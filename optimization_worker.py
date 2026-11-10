import os
import sys
import pandas as pd
import numpy as np
pd.DataFrame.iteritems = pd.DataFrame.items
from backtesting import Strategy
from backtesting.lib import FractionalBacktest

def calc_ema_series(series, span):
    return pd.Series(series).ewm(span=span, adjust=False).mean().values

def calc_atr_series(high, low, close, period=14):
    high_s = pd.Series(high)
    low_s = pd.Series(low)
    close_s = pd.Series(close)
    close_prev = close_s.shift(1)
    tr = pd.concat([
        high_s - low_s,
        (high_s - close_prev).abs(),
        (low_s - close_prev).abs()
    ], axis=1).max(axis=1)
    return pd.Series(tr).ewm(span=period, adjust=False).mean().values

class OptMTFStrategy(Strategy):
    mode = 'long_only'
    atr_mult = 6.0
    cooldown_bars = 7
    min_profit_pct = 0.010
    ema_micro_span = 33
    atr_period_span = 14

    def init(self):
        self.ema_micro = self.I(calc_ema_series, self.data.Close, self.ema_micro_span, overlay=True)
        self.atr = self.I(calc_atr_series, self.data.High, self.data.Low, self.data.Close, self.atr_period_span, overlay=False)
        self.macro_bullish = self.I(lambda: self.data.df['macro_bullish'].values, overlay=False)
        self.macro_bull_alive = self.I(lambda: self.data.df['macro_bull_alive'].values, overlay=False)
        self.bars_since_exit = 999
        self.trailing_sl = 0.0
        self.entry_price = 0.0

    def next(self):
        if len(self.data) < self.ema_micro_span:
            return

        if not self.position:
            self.bars_since_exit += 1
            if self.bars_since_exit >= self.cooldown_bars:
                long_trigger = (
                    self.macro_bullish[-1] and
                    (self.data.Low[-2] <= self.ema_micro[-2]) and
                    (self.data.Close[-1] > self.ema_micro[-1]) and
                    (self.ema_micro[-1] >= self.ema_micro[-2])
                )
                if long_trigger:
                    self.buy(size=0.9999)
                    self.entry_price = self.data.Close[-1]
                    self.trailing_sl = self.entry_price - (self.atr_mult * self.atr[-1])
        else:
            is_in_profit = self.data.Close[-1] >= (self.entry_price * (1.0 + self.min_profit_pct))
            if is_in_profit:
                new_sl = self.data.Close[-1] - (self.atr_mult * self.atr[-1])
                self.trailing_sl = max(self.trailing_sl, new_sl)

            if self.data.Close[-1] <= self.trailing_sl:
                self.position.close()
                self.bars_since_exit = 0
                return

            if not self.macro_bull_alive[-1]:
                self.position.close()
                self.bars_since_exit = 0
                return

PRELOADED_DATA = {}

def init_worker(preloaded_dict):
    global PRELOADED_DATA
    PRELOADED_DATA = preloaded_dict

def evaluate_combination_task(combo_tuple):
    p_spread, p_ema_micro, p_atr_period, p_atr_mult, p_cooldown, p_min_profit = combo_tuple

    class TargetStrat(OptMTFStrategy):
        atr_mult = p_atr_mult
        cooldown_bars = p_cooldown
        min_profit_pct = p_min_profit
        ema_micro_span = p_ema_micro
        atr_period_span = p_atr_period

    asset_returns = {}
    asset_mdds = {}
    asset_trades = {}

    for asset in ['SPY', 'QQQ', 'DJI']:
        base_df = PRELOADED_DATA[asset].copy(deep=False)
        base_df['macro_bullish'] = base_df['ema_fast'] > (base_df['ema_slow'] * (1.0 + p_spread))

        bt = FractionalBacktest(
            base_df,
            TargetStrat,
            cash=1000.0,
            commission=0.0003,
            trade_on_close=True,
            finalize_trades=True,
            fractional_unit=1e-4
        )
        stats = bt.run()

        ret = float(stats['Return [%]'])
        mdd = float(stats['Max. Drawdown [%]'])
        tr = int(stats['# Trades'])

        asset_returns[asset] = ret
        asset_mdds[asset] = mdd
        asset_trades[asset] = tr

    avg_return = (asset_returns['SPY'] + asset_returns['QQQ'] + asset_returns['DJI']) / 3.0
    avg_mdd = (asset_mdds['SPY'] + asset_mdds['QQQ'] + asset_mdds['DJI']) / 3.0

    return {
        'macro_spread_threshold': p_spread,
        'ema_micro': p_ema_micro,
        'atr_period': p_atr_period,
        'atr_mult': p_atr_mult,
        'cooldown_bars': p_cooldown,
        'min_profit_pct': p_min_profit,
        'Avg_Total_Return': round(avg_return, 2),
        'Avg_Max_Drawdown': round(avg_mdd, 2),
        'SPY_Return (%)': round(asset_returns['SPY'], 2),
        'QQQ_Return (%)': round(asset_returns['QQQ'], 2),
        'DJI_Return (%)': round(asset_returns['DJI'], 2),
        'SPY_MaxDD (%)': round(asset_mdds['SPY'], 2),
        'QQQ_MaxDD (%)': round(asset_mdds['QQQ'], 2),
        'DJI_MaxDD (%)': round(asset_mdds['DJI'], 2),
        'SPY_Trades': asset_trades['SPY'],
        'QQQ_Trades': asset_trades['QQQ'],
        'DJI_Trades': asset_trades['DJI'],
    }
