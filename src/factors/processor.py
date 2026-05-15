from __future__ import annotations

import pandas as pd
import numpy as np


class FactorProcessor:
    """
    因子处理器。

    作用：
    1. 处理原始因子值中的缺失值、极端值；
    2. 对因子进行横截面标准化；
    3. 统一因子方向；
    4. 生成排名和百分位分数；
    5. 为后续多因子合成、组合构建和回测提供标准输入。

    标准输入格式建议为：
        ts_code
        trade_date
        factor_value
        factor_name

    标准输出会在原始 DataFrame 基础上新增处理后的列。
    """

    def __init__(self):
        pass

    @staticmethod
    def drop_missing(
        df: pd.DataFrame,
        value_col: str = "factor_value"
    ) -> pd.DataFrame:
        """
        删除因子值缺失的记录。

        参数
        ----
        df:
            原始因子数据。

        value_col:
            因子值所在列名，默认是 factor_value。

        返回
        ----
        删除缺失值后的 DataFrame。

        使用场景
        ----
        对于动量、波动率等需要历史窗口的因子，
        前若干天通常会因为历史数据不足而产生 NaN。
        这些记录不能参与横截面排序。
        """

        if df.empty:
            return df

        result = df.dropna(subset=[value_col]).copy()
        return result

    @staticmethod
    def winsorize_by_date(
        df: pd.DataFrame,
        value_col: str = "factor_value",
        lower_quantile: float = 0.01,
        upper_quantile: float = 0.99,
        output_col: str = "factor_winsorized"
    ) -> pd.DataFrame:
        """
        按交易日进行横截面去极值处理。

        参数
        ----
        df:
            原始因子数据。

        value_col:
            原始因子值列名。

        lower_quantile:
            下分位数阈值，默认 1%。

        upper_quantile:
            上分位数阈值，默认 99%。

        output_col:
            去极值后的输出列名。

        返回
        ----
        新增 output_col 的 DataFrame。

        说明
        ----
        去极值不是删除极端值，而是把极端值压到分位数边界。
        这样可以降低异常值对标准化和多因子合成的影响。
        """

        if df.empty:
            return df

        result = df.copy()

        def _clip_one_day(x: pd.Series) -> pd.Series:
            lower = x.quantile(lower_quantile)
            upper = x.quantile(upper_quantile)
            return x.clip(lower=lower, upper=upper)

        result[output_col] = (
            result.groupby("trade_date")[value_col]
            .transform(_clip_one_day)
        )

        return result

    @staticmethod
    def zscore_by_date(
        df: pd.DataFrame,
        value_col: str = "factor_winsorized",
        output_col: str = "factor_zscore"
    ) -> pd.DataFrame:
        """
        按交易日进行横截面 Z-score 标准化。

        参数
        ----
        df:
            因子数据。

        value_col:
            需要标准化的列名，默认使用去极值后的 factor_winsorized。

        output_col:
            标准化后的输出列名。

        返回
        ----
        新增 output_col 的 DataFrame。

        说明
        ----
        Z-score 公式：
            z = (x - mean) / std

        这样可以把不同量纲的因子转成可比较的标准分数。
        比如动量是收益率，PB 是倍数，ROE 是百分比，
        经过标准化后可以放在同一个多因子模型里合成。

        注意
        ----
        如果某一天横截面标准差为 0，则该日无法标准化，
        这里返回 NaN，后续再统一处理。
        """

        if df.empty:
            return df

        result = df.copy()

        def _zscore_one_day(x: pd.Series) -> pd.Series:
            mean = x.mean()
            std = x.std(ddof=0)

            if std == 0 or pd.isna(std):
                return pd.Series(np.nan, index=x.index)

            return (x - mean) / std

        result[output_col] = (
            result.groupby("trade_date")[value_col]
            .transform(_zscore_one_day)
        )

        return result

    @staticmethod
    def apply_direction(
        df: pd.DataFrame,
        value_col: str = "factor_zscore",
        direction: str = "positive",
        output_col: str = "factor_score"
    ) -> pd.DataFrame:
        """
        统一因子方向。

        参数
        ----
        df:
            因子数据。

        value_col:
            需要调整方向的列名。

        direction:
            因子方向。

            positive:
                因子值越大越好。
                例如动量因子、ROE 因子。

            negative:
                因子值越小越好。
                例如 PE、PB、波动率因子。

        output_col:
            方向统一后的输出列名。

        返回
        ----
        新增 output_col 的 DataFrame。

        说明
        ----
        多因子合成前必须统一方向。
        例如：
            动量越高越好，方向是 positive；
            PB 越低越好，方向是 negative。

        对 negative 因子，直接乘以 -1，
        这样所有因子都变成“分数越高越好”。
        """

        if df.empty:
            return df

        if direction not in ["positive", "negative"]:
            raise ValueError("direction must be one of: 'positive', 'negative'")

        result = df.copy()

        if direction == "positive":
            result[output_col] = result[value_col]
        else:
            result[output_col] = -result[value_col]

        return result

    @staticmethod
    def rank_by_date(
        df: pd.DataFrame,
        value_col: str = "factor_score",
        rank_col: str = "factor_rank",
        percentile_col: str = "factor_percentile"
    ) -> pd.DataFrame:
        """
        按交易日进行横截面排名。

        参数
        ----
        df:
            因子数据。

        value_col:
            用于排名的列名。通常是 factor_score。
            此时已经完成方向统一，所以默认含义是“越大越好”。

        rank_col:
            整数排名列名。
            1 表示当天横截面里因子分数最高，也就是最好。

        percentile_col:
            百分位分数列名。
            取值范围 0~1，越接近 1 表示越好。

        返回
        ----
        新增 rank_col 和 percentile_col 的 DataFrame。

        说明
        ----
        factor_rank：
            用于查看具体名次，1 表示最好。

        factor_percentile：
            用于选股更直观，越接近 1 越好。
            例如 factor_percentile >= 0.95 表示选择当天因子排名前 5% 的股票。
        """

        if df.empty:
            return df

        result = df.copy()

        # 整数排名：1 表示最好。
        result[rank_col] = (
            result.groupby("trade_date")[value_col]
            .rank(ascending=False, method="average")
        )

        # 百分位分数：越接近 1 表示越好。
        # 注意这里用 ascending=True，是为了让分数越高的股票百分位越接近 1。
        result[percentile_col] = (
            result.groupby("trade_date")[value_col]
            .rank(ascending=True, pct=True, method="average")
        )

        return result

    @staticmethod
    def filter_min_count_by_date(
        df: pd.DataFrame,
        value_col: str = "factor_value",
        min_count: int = 100
    ) -> pd.DataFrame:
        """
        过滤横截面样本数量过少的交易日。

        参数
        ----
        df:
            因子数据。

        value_col:
            用于判断有效样本的列名。

        min_count:
            某个交易日至少需要多少个有效股票样本。

        返回
        ----
        删除样本数量过少交易日后的 DataFrame。

        使用场景
        ----
        如果某天只有少数股票有因子值，
        那么这一天的横截面排名和标准化没有统计意义。
        """

        if df.empty:
            return df

        result = df.copy()

        count_by_date = (
            result.dropna(subset=[value_col])
            .groupby("trade_date")["ts_code"]
            .count()
        )

        valid_dates = count_by_date[
            count_by_date >= min_count
        ].index

        result = result[
            result["trade_date"].isin(valid_dates)
        ].copy()

        return result

    @staticmethod
    def neutral_fill_na(
        df: pd.DataFrame,
        value_col: str = "factor_score",
        output_col: str = "factor_score_filled",
        fill_value: float = 0.0
    ) -> pd.DataFrame:
        """
        用中性值填充处理后的因子缺失值。

        参数
        ----
        df:
            因子数据。

        value_col:
            需要填充的列名。

        output_col:
            填充后的输出列名。

        fill_value:
            填充值，默认 0。

        返回
        ----
        新增 output_col 的 DataFrame。

        说明
        ----
        对已经做过 Z-score 的因子来说，
        0 通常代表横截面平均水平。
        因此用 0 填充可以理解为“不给这个股票额外正面或负面信号”。

        注意
        ----
        原始因子缺失时，不一定应该直接填充。
        更推荐先完成去极值、标准化、方向统一之后，
        再对最终分数做中性填充。
        """

        if df.empty:
            return df

        result = df.copy()
        result[output_col] = result[value_col].fillna(fill_value)

        return result

    def process_single_factor(
        self,
        df: pd.DataFrame,
        value_col: str = "factor_value",
        direction: str = "positive",
        winsorize: bool = True,
        standardize: bool = True,
        rank: bool = True,
        lower_quantile: float = 0.01,
        upper_quantile: float = 0.99,
        drop_na: bool = True,
        min_count: int | None = None
    ) -> pd.DataFrame:
        """
        单因子标准处理流水线。

        参数
        ----
        df:
            原始因子数据，至少包含：
            ts_code, trade_date, factor_value。

        value_col:
            原始因子值列名。

        direction:
            因子方向：
            positive 表示越大越好；
            negative 表示越小越好。

        winsorize:
            是否进行去极值。

        standardize:
            是否进行 Z-score 标准化。

        rank:
            是否生成横截面排名和百分位分数。

        lower_quantile, upper_quantile:
            去极值分位数。

        drop_na:
            是否删除原始因子值为空的记录。

        min_count:
            是否过滤横截面样本数量过少的交易日。
            None 表示不过滤。

        返回
        ----
        处理后的因子 DataFrame。

        输出字段通常包括：
            factor_value
            factor_winsorized
            factor_zscore
            factor_score
            factor_rank
            factor_percentile

        说明
        ----
        这是后面最常用的入口函数。
        单个因子从原始值到可交易分数，默认都走这个流程。
        """

        if df.empty:
            return df

        result = df.copy()

        # 统一日期格式，避免 groupby 时出现字符串/时间混乱。
        result["trade_date"] = pd.to_datetime(result["trade_date"])

        # 第一步：删除原始因子值缺失的记录。
        if drop_na:
            result = self.drop_missing(
                result,
                value_col=value_col
            )

        # 第二步：过滤样本数量过少的交易日。
        if min_count is not None:
            result = self.filter_min_count_by_date(
                result,
                value_col=value_col,
                min_count=min_count
            )

        # 第三步：去极值。
        if winsorize:
            result = self.winsorize_by_date(
                result,
                value_col=value_col,
                lower_quantile=lower_quantile,
                upper_quantile=upper_quantile,
                output_col="factor_winsorized"
            )
            current_col = "factor_winsorized"
        else:
            current_col = value_col

        # 第四步：横截面标准化。
        if standardize:
            result = self.zscore_by_date(
                result,
                value_col=current_col,
                output_col="factor_zscore"
            )
            current_col = "factor_zscore"

        # 第五步：统一因子方向。
        result = self.apply_direction(
            result,
            value_col=current_col,
            direction=direction,
            output_col="factor_score"
        )

        # 第六步：生成横截面排名和百分位分数。
        if rank:
            result = self.rank_by_date(
                result,
                value_col="factor_score",
                rank_col="factor_rank",
                percentile_col="factor_percentile"
            )

        # 第七步：统一排序并重置索引，保证输出整洁稳定。
        result = result.sort_values(
            ["trade_date", "ts_code"]
        ).reset_index(drop=True)

        return result