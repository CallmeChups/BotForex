//+------------------------------------------------------------------+
//|                                          FractalZigzagLines.mq5  |
//|  Fractal markers (yellow/magenta diamonds) + blue line linking   |
//|  consecutive fractal highs + red line linking fractal lows.      |
//|  v1.10: separate bar count for Fractal markers and ZigZag lines. |
//|  v1.20: breakout line - when price breaks the nearest fractal    |
//|         high/low, a straight line runs from the broken fractal   |
//|         to N candles past the breaking candle; next one replaces.|
//+------------------------------------------------------------------+
#property copyright "FractalZigzagLines"
#property version   "1.22"
#property indicator_chart_window
#property indicator_buffers 8
#property indicator_plots   8

//--- plot 0: fractal high markers
#property indicator_label1  "Fractal High"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrYellow
#property indicator_width1  1
//--- plot 1: fractal low markers
#property indicator_label2  "Fractal Low"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrMagenta
#property indicator_width2  1
//--- plot 2: line linking fractal highs
#property indicator_label3  "High Line"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrDodgerBlue
#property indicator_style3  STYLE_SOLID
#property indicator_width3  2
//--- plot 3: line linking fractal lows
#property indicator_label4  "Low Line"
#property indicator_type4   DRAW_LINE
#property indicator_color4  clrRed
#property indicator_style4  STYLE_SOLID
#property indicator_width4  2

//--- plot 4/5: nearest fractal high / low -> current bar
#property indicator_label5  "Nearest High"
#property indicator_type5   DRAW_LINE
#property indicator_color5  clrLime
#property indicator_label6  "Nearest Low"
#property indicator_type6   DRAW_LINE
#property indicator_color6  clrLime

//--- plot 6/7: breakout line (upside break / downside break)
#property indicator_label7  "Break Up"
#property indicator_type7   DRAW_LINE
#property indicator_color7  clrAqua
#property indicator_label8  "Break Down"
#property indicator_type8   DRAW_LINE
#property indicator_color8  clrOrange

//--- inputs
enum ENUM_FRACTAL_SHAPE
  {
   SHAPE_DOT     = 0,  // Dot - cham tron (code 159)
   SHAPE_DIAMOND = 1,  // Diamond - hinh thoi (code 108)
   SHAPE_SQUARE  = 2,  // Square - hinh vuong (code 110)
   SHAPE_ARROW   = 3,  // Arrow - mui ten len/xuong (233/234)
   SHAPE_STYLE158= 4,  // Style 158 (Wingdings code 158)
   SHAPE_X       = 5   // X - dau nhan (Wingdings code 251)
  };

input int    InpStrength   = 2;            // Bars each side of a fractal
input int    InpMaxBars    = 1000;         // Fractal: number of bars displayed (markers)
input int    InpZigBars    = 300;          // ZigZag: number of bars displayed (lines, independent of Fractal)
input bool   InpShowMarkers= true;         // Show diamond markers
input bool   InpShowLines  = true;         // Show connecting lines
input ENUM_FRACTAL_SHAPE InpHighShape = SHAPE_DIAMOND; // Fractal HIGH shape
input ENUM_FRACTAL_SHAPE InpLowShape  = SHAPE_DIAMOND; // Fractal LOW shape
input int    InpHighSize   = 1;            // Fractal HIGH size (1-5)
input int    InpLowSize    = 1;            // Fractal LOW size (1-5)
input int    InpShiftPx    = 0;            // Marker gap from high/low (pixels, same on all TFs)
input color  InpHighColor  = clrYellow;    // Fractal high marker color
input color  InpLowColor   = clrMagenta;   // Fractal low marker color
input color  InpHighLine   = clrDodgerBlue;// High line color
input color  InpLowLine    = clrRed;       // Low line color
input int    InpLineWidth  = 2;            // Line width
input ENUM_LINE_STYLE InpLineStyle = STYLE_SOLID; // Line style
input bool   InpShowNearest = true;        // Show nearest high/low horizontal lines to current bar
input color  InpNearHighClr = clrLime;     // Nearest high line color
input color  InpNearLowClr  = clrLime;     // Nearest low line color
input int    InpNearWidth   = 1;           // Nearest lines width
input ENUM_LINE_STYLE InpNearStyle = STYLE_SOLID; // Nearest lines style

//--- breakout line
input bool   InpShowBreak   = true;        // Show breakout line (price breaks nearest fractal high/low)
input bool   InpBreakByClose= false;       // Break confirmed by candle CLOSE (false = wick/high-low)
input int    InpBreakExtend = 3;           // Extend line N candles past the breaking candle
input color  InpBreakUpClr  = clrAqua;     // Break-up line color (broke a fractal high)
input color  InpBreakDnClr  = clrOrange;   // Break-down line color (broke a fractal low)
input int    InpBreakWidth  = 2;           // Breakout line width
input ENUM_LINE_STYLE InpBreakStyle = STYLE_SOLID; // Breakout line style

//--- time markers (vertical lines repeated every trading day)
input bool   InpTimeOn     = true;         // Show time markers (vertical lines)
input string InpTime1      = "00:00";      // Time 1 (HH:MM, empty = off)
input string InpTime2      = "01:00";      // Time 2 (HH:MM, empty = off)
input string InpTime3      = "03:00";      // Time 3 (HH:MM, empty = off)
input string InpTime4      = "05:30";      // Time 4 (HH:MM, empty = off)
input string InpTime5      = "07:00";      // Time 5 (HH:MM, empty = off)
input string InpTime6      = "11:00";      // Time 6 (HH:MM, empty = off)
input string InpTime7      = "12:00";      // Time 7 (HH:MM, empty = off)
input string InpTime8      = "13:30";      // Time 8 (HH:MM, empty = off)
input string InpTime9      = "14:30";      // Time 9 (HH:MM, empty = off)
input string InpTime10     = "16:30";      // Time 10 (HH:MM, empty = off)
input int    InpTimeDays   = 5;            // Number of trading days to show
input color  InpTimeColor  = clrDimGray;   // Time line color
input int    InpTimeWidth  = 1;            // Time line width (1-5)
input ENUM_LINE_STYLE InpTimeStyle = STYLE_DOT; // Time line style
input bool   InpTimeBack   = true;         // Draw behind candles
input bool   InpTimeSelect = false;        // Selectable / draggable

double bufHighMark[];
double bufLowMark[];
double bufHighLine[];
double bufLowLine[];
double bufNearHigh[];
double bufNearLow[];
double bufBreakUp[];
double bufBreakDn[];

#define TM_PREFIX "FZL_TM_"
int N;
datetime g_lastDay = 0;
int g_lastTotal = 0;
int g_prevFirst = 0;

//--- breakout state: active (most recent) fractal high/low and the latest breakout event
int    g_hBar = -1;      // bar of the active fractal high
double g_hPrc = 0;       // its price
bool   g_hBroken = true; // already broken?
int    g_lBar = -1;
double g_lPrc = 0;
bool   g_lBroken = true;
int    g_evDir = 0;      // latest event: +1 = broke a high, -1 = broke a low, 0 = none
int    g_evBar = -1;     // bar of the fractal that was broken
double g_evPrc = 0;      // price of the broken fractal
int    g_evEnd = -1;     // bar of the candle that broke it (line stops here)

//+------------------------------------------------------------------+
int ShapeCode(ENUM_FRACTAL_SHAPE shape, bool isHigh)
  {
   switch(shape)
     {
      case SHAPE_DOT:      return(159);
      case SHAPE_DIAMOND:  return(108);
      case SHAPE_SQUARE:   return(110);
      case SHAPE_ARROW:    return(isHigh ? 234 : 233);
      case SHAPE_STYLE158: return(158);
      default:             return(251);
     }
  }

//+------------------------------------------------------------------+
//| Marker shape / size / color / gap (re-applied on every full calc)  |
//+------------------------------------------------------------------+
void ApplyMarkerStyle()
  {
   PlotIndexSetInteger(0, PLOT_DRAW_TYPE, InpShowMarkers ? DRAW_ARROW : DRAW_NONE);
   PlotIndexSetInteger(1, PLOT_DRAW_TYPE, InpShowMarkers ? DRAW_ARROW : DRAW_NONE);
   PlotIndexSetInteger(0, PLOT_ARROW, ShapeCode(InpHighShape, true));
   PlotIndexSetInteger(1, PLOT_ARROW, ShapeCode(InpLowShape, false));
   PlotIndexSetInteger(0, PLOT_ARROW_SHIFT, -InpShiftPx);  // negative = up
   PlotIndexSetInteger(1, PLOT_ARROW_SHIFT,  InpShiftPx);  // positive = down
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, InpHighColor);
   PlotIndexSetInteger(1, PLOT_LINE_COLOR, InpLowColor);
   PlotIndexSetInteger(0, PLOT_LINE_WIDTH, MathMax(1, MathMin(5, InpHighSize)));
   PlotIndexSetInteger(1, PLOT_LINE_WIDTH, MathMax(1, MathMin(5, InpLowSize)));
  }

//+------------------------------------------------------------------+
//| Vertical time markers: same HH:MM lines on the last N trading days |
//+------------------------------------------------------------------+
void DrawTimeMarks(const datetime latest)
  {
   ObjectsDeleteAll(0, TM_PREFIX);
   if(!InpTimeOn)
      return;

   string t[10];
   t[0]=InpTime1; t[1]=InpTime2; t[2]=InpTime3; t[3]=InpTime4; t[4]=InpTime5;
   t[5]=InpTime6; t[6]=InpTime7; t[7]=InpTime8; t[8]=InpTime9; t[9]=InpTime10;

   int mins[10];
   int n = 0;
   for(int k = 0; k < 10; k++)
     {
      string x = t[k];
      StringTrimLeft(x);
      StringTrimRight(x);
      if(x == "")
         continue;
      string parts[];
      if(StringSplit(x, ':', parts) != 2)
         continue;
      int h = (int)StringToInteger(parts[0]);
      int m = (int)StringToInteger(parts[1]);
      if(h < 0 || h > 23 || m < 0 || m > 59)
         continue;
      mins[n++] = h * 60 + m;
     }
   if(n == 0)
      return;

   datetime day   = latest - (latest % 86400);
   int      shown = 0;
   int      width = MathMax(1, MathMin(5, InpTimeWidth));

   for(int d = 0; d < 40 && shown < InpTimeDays; d++)
     {
      datetime base = day - (datetime)d * 86400;
      MqlDateTime dt;
      TimeToStruct(base, dt);
      if(dt.day_of_week == 0 || dt.day_of_week == 6)   // skip weekends
         continue;
      shown++;
      for(int j = 0; j < n; j++)
        {
         datetime tt   = base + (datetime)mins[j] * 60;
         string   name = TM_PREFIX + IntegerToString((long)tt);
         if(ObjectFind(0, name) >= 0)
            continue;
         if(!ObjectCreate(0, name, OBJ_VLINE, 0, tt, 0))
            continue;
         ObjectSetInteger(0, name, OBJPROP_COLOR, InpTimeColor);
         ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
         ObjectSetInteger(0, name, OBJPROP_STYLE, InpTimeStyle);
         ObjectSetInteger(0, name, OBJPROP_BACK, InpTimeBack);
         ObjectSetInteger(0, name, OBJPROP_SELECTABLE, InpTimeSelect);
         ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
        }
     }
   ChartRedraw();
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, TM_PREFIX);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   N = MathMax(1, InpStrength);
   g_lastTotal = 0;
   g_prevFirst = 0;
   g_lastDay   = 0;

   g_hBar = -1; g_hPrc = 0; g_hBroken = true;
   g_lBar = -1; g_lPrc = 0; g_lBroken = true;
   g_evDir = 0; g_evBar = -1; g_evPrc = 0; g_evEnd = -1;

   SetIndexBuffer(0, bufHighMark, INDICATOR_DATA);
   SetIndexBuffer(1, bufLowMark,  INDICATOR_DATA);
   SetIndexBuffer(2, bufHighLine, INDICATOR_DATA);
   SetIndexBuffer(3, bufLowLine,  INDICATOR_DATA);
   SetIndexBuffer(4, bufNearHigh, INDICATOR_DATA);
   SetIndexBuffer(5, bufNearLow,  INDICATOR_DATA);
   SetIndexBuffer(6, bufBreakUp,  INDICATOR_DATA);
   SetIndexBuffer(7, bufBreakDn,  INDICATOR_DATA);

   for(int p = 0; p < 8; p++)
      PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   ApplyMarkerStyle();

   //--- lines
   PlotIndexSetInteger(2, PLOT_LINE_COLOR, InpHighLine);
   PlotIndexSetInteger(3, PLOT_LINE_COLOR, InpLowLine);
   for(int p = 2; p < 4; p++)
     {
      PlotIndexSetInteger(p, PLOT_LINE_WIDTH, InpLineWidth);
      PlotIndexSetInteger(p, PLOT_LINE_STYLE, InpLineStyle);
      PlotIndexSetInteger(p, PLOT_DRAW_TYPE, InpShowLines ? DRAW_LINE : DRAW_NONE);
     }

   //--- nearest lines
   PlotIndexSetInteger(4, PLOT_LINE_COLOR, InpNearHighClr);
   PlotIndexSetInteger(5, PLOT_LINE_COLOR, InpNearLowClr);
   for(int p = 4; p < 6; p++)
     {
      PlotIndexSetInteger(p, PLOT_LINE_WIDTH, InpNearWidth);
      PlotIndexSetInteger(p, PLOT_LINE_STYLE, InpNearStyle);
      PlotIndexSetInteger(p, PLOT_DRAW_TYPE, InpShowNearest ? DRAW_LINE : DRAW_NONE);
     }

   //--- breakout lines
   PlotIndexSetInteger(6, PLOT_LINE_COLOR, InpBreakUpClr);
   PlotIndexSetInteger(7, PLOT_LINE_COLOR, InpBreakDnClr);
   for(int p = 6; p < 8; p++)
     {
      PlotIndexSetInteger(p, PLOT_LINE_WIDTH, MathMax(1, MathMin(5, InpBreakWidth)));
      PlotIndexSetInteger(p, PLOT_LINE_STYLE, InpBreakStyle);
      PlotIndexSetInteger(p, PLOT_DRAW_TYPE, InpShowBreak ? DRAW_LINE : DRAW_NONE);
     }

   IndicatorSetString(INDICATOR_SHORTNAME, "FractalZigzagLines(" + IntegerToString(N) + ")");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Fill a straight segment (a,pa) -> (b,pb) bar by bar               |
//+------------------------------------------------------------------+
void FillSeg(double &buf[], int a, double pa, int b, double pb)
  {
   if(b <= a) { buf[a] = pa; return; }
   for(int k = a; k <= b; k++)
      buf[k] = pa + (pb - pa) * (double)(k - a) / (double)(b - a);
  }

//+------------------------------------------------------------------+
//| First bar after "from" (up to "to") whose price crosses the level |
//| up=true : high > level ; up=false : low < level                   |
//+------------------------------------------------------------------+
int CrossBar(const double &arr[], int from, int to, double level, bool up)
  {
   for(int k = from + 1; k <= to; k++)
      if(up ? arr[k] > level : arr[k] < level)
         return(k);
   return(to);
  }

//+------------------------------------------------------------------+
//| Does bar k break the active fractal high / low? Updates the event |
//+------------------------------------------------------------------+
void CheckBreakBar(const int k, const double &high[], const double &low[], const double &close[])
  {
   if(g_hBar >= 0 && !g_hBroken)
     {
      double v = InpBreakByClose ? close[k] : high[k];
      if(v > g_hPrc)
        {
         g_hBroken = true;
         g_evDir = 1;
         g_evBar = g_hBar;
         g_evPrc = g_hPrc;
         g_evEnd = k;
        }
     }
   if(g_lBar >= 0 && !g_lBroken)
     {
      double v = InpBreakByClose ? close[k] : low[k];
      if(v < g_lPrc)
        {
         g_lBroken = true;
         g_evDir = -1;
         g_evBar = g_lBar;
         g_evPrc = g_lPrc;
         g_evEnd = k;
        }
     }
  }

//+------------------------------------------------------------------+
void ScanBreaks(const int from, const int to, const double &high[], const double &low[], const double &close[])
  {
   for(int k = from; k <= to; k++)
      CheckBreakBar(k, high, low, close);
  }

//+------------------------------------------------------------------+
//| Draw the latest breakout line: broken fractal -> breaking candle +N|
//+------------------------------------------------------------------+
void DrawBreak(const int total)
  {
   if(!InpShowBreak || g_evDir == 0 || g_evBar < 0)
      return;
   int endBar = MathMin(g_evEnd + MathMax(0, InpBreakExtend), total - 1);   // breaking candle + N, capped at latest bar
   if(g_evDir > 0)
      FillSeg(bufBreakUp, g_evBar, g_evPrc, endBar, g_evPrc);
   else
      FillSeg(bufBreakDn, g_evBar, g_evPrc, endBar, g_evPrc);
  }

//+------------------------------------------------------------------+
//| Cheap per-tick check (same bar): only tests the current candle    |
//+------------------------------------------------------------------+
void TickBreakUpdate(const int total, const double &high[], const double &low[], const double &close[])
  {
   if(!InpShowBreak)
      return;
   int oldDir = g_evDir;
   int oldBar = g_evBar;
   CheckBreakBar(total - 1, high, low, close);
   if(g_evDir == oldDir && g_evBar == oldBar)
      return;   // no new breakout

   //--- new breakout: delete the old line, draw the new one
   int from = MathMax(0, MathMin(oldBar < 0 ? total - 1 : oldBar, g_evBar));
   ArrayFill(bufBreakUp, from, total - from, EMPTY_VALUE);
   ArrayFill(bufBreakDn, from, total - from, EMPTY_VALUE);
   DrawBreak(total);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total < 2 * N + 1)
      return(0);

   //--- structure depends on previous vertices: recalc the window only on a new bar
   if(prev_calculated != 0 && rates_total == g_lastTotal)
     {
      TickBreakUpdate(rates_total, high, low, close);   // real-time breakout check (very cheap)
      return(rates_total);
     }
   g_lastTotal = rates_total;

   //--- rebuild time markers on full recalc or when a new day starts (cheap: at most ~10 x days objects)
   datetime curDay = time[rates_total - 1] - (time[rates_total - 1] % 86400);
   if(prev_calculated == 0 || curDay != g_lastDay)
     {
      DrawTimeMarks(time[rates_total - 1]);
      g_lastDay = curDay;
     }

   if(prev_calculated == 0)
      ApplyMarkerStyle();

   //--- two independent display windows
   int firstF = MathMax(N, rates_total - MathMax(1, InpMaxBars));   // fractal markers window
   int firstZ = MathMax(N, rates_total - MathMax(1, InpZigBars));   // zigzag lines window
   int first  = MathMin(firstF, firstZ);                            // scan from the earlier one
   int last   = rates_total - 1 - N;                                // last bar that can be confirmed

   //--- clear ONLY the window that is recalculated (not the whole history)
   int clearFrom = (prev_calculated == 0) ? 0 : MathMax(0, MathMin(g_prevFirst, first));
   int clearCnt  = rates_total - clearFrom;
   ArrayFill(bufHighMark, clearFrom, clearCnt, EMPTY_VALUE);
   ArrayFill(bufLowMark,  clearFrom, clearCnt, EMPTY_VALUE);
   ArrayFill(bufHighLine, clearFrom, clearCnt, EMPTY_VALUE);
   ArrayFill(bufLowLine,  clearFrom, clearCnt, EMPTY_VALUE);
   ArrayFill(bufNearHigh, clearFrom, clearCnt, EMPTY_VALUE);
   ArrayFill(bufNearLow,  clearFrom, clearCnt, EMPTY_VALUE);
   ArrayFill(bufBreakUp,  clearFrom, clearCnt, EMPTY_VALUE);
   ArrayFill(bufBreakDn,  clearFrom, clearCnt, EMPTY_VALUE);
   g_prevFirst = first;

   // zigzag chain state (only fed by fractals inside the ZigZag window)
   int    hCnt = 0, lCnt = 0;
   int    hBar = -1, lBar = -1;
   double hPrc = 0, lPrc = 0;

   // nearest fractal state (independent of both windows)
   int    nhBar = -1, nlBar = -1;
   double nhPrc = 0,  nlPrc = 0;

   // breakout state reset (rebuilt from scratch in the same pass)
   g_hBar = -1; g_hPrc = 0; g_hBroken = true;
   g_lBar = -1; g_lPrc = 0; g_lBroken = true;
   g_evDir = 0; g_evBar = -1; g_evPrc = 0; g_evEnd = -1;
   int scanned = first - 1;   // last bar already checked for breakouts

   for(int i = first; i <= last; i++)
     {
      bool isHigh = true, isLow = true;
      for(int k = 1; k <= N; k++)
        {
         if(isHigh && !(high[i] > high[i - k] && high[i] >= high[i + k])) isHigh = false;
         if(isLow  && !(low[i]  < low[i - k]  && low[i]  <= low[i + k]))  isLow  = false;
         if(!isHigh && !isLow) break;
        }

      bool inF = (i >= firstF);
      bool inZ = (i >= firstZ);

      //--- a fractal at i is confirmed at bar i+N: test breakouts of the OLD levels up to that bar first
      if(isHigh || isLow)
        {
         int conf = i + N;
         ScanBreaks(scanned + 1, conf, high, low, close);
         scanned = conf;
        }

      if(isHigh)
        {
         if(inF) bufHighMark[i] = high[i];
         nhBar = i;
         nhPrc = high[i];
         g_hBar = i; g_hPrc = high[i]; g_hBroken = false;   // new nearest high

         if(inZ)
           {
            if(hCnt >= 1 && high[i] < hPrc)
              {  // lower high: chain continues (diagonal)
               FillSeg(bufHighLine, hBar, hPrc, i, high[i]);
               hCnt++;
              }
            else
              {  // higher/equal high: chain broken
               if(hCnt >= 2)
                  FillSeg(bufHighLine, hBar, hPrc, CrossBar(high, hBar, i, hPrc, true), hPrc);   // horizontal until a candle crosses it
               hCnt = 1;
              }
            hBar = i;
            hPrc = high[i];
           }
        }

      if(isLow)
        {
         if(inF) bufLowMark[i] = low[i];
         nlBar = i;
         nlPrc = low[i];
         g_lBar = i; g_lPrc = low[i]; g_lBroken = false;    // new nearest low

         if(inZ)
           {
            if(lCnt >= 1 && low[i] > lPrc)
              {  // higher low: chain continues (diagonal)
               FillSeg(bufLowLine, lBar, lPrc, i, low[i]);
               lCnt++;
              }
            else
              {  // lower/equal low: chain broken
               if(lCnt >= 2)
                  FillSeg(bufLowLine, lBar, lPrc, CrossBar(low, lBar, i, lPrc, false), lPrc);    // horizontal until a candle crosses it
               lCnt = 1;
              }
            lBar = i;
            lPrc = low[i];
           }
        }
     }

   //--- unfinished chains: horizontal runs until a candle crosses it (or to the latest bar)
   if(hCnt >= 2)
      FillSeg(bufHighLine, hBar, hPrc, CrossBar(high, hBar, rates_total - 1, hPrc, true), hPrc);
   if(lCnt >= 2)
      FillSeg(bufLowLine, lBar, lPrc, CrossBar(low, lBar, rates_total - 1, lPrc, false), lPrc);

   //--- nearest (most recent) fractal high/low -> horizontal line to the current bar.
   //--- Buffers are rebuilt on every new bar, so the old line disappears when a new fractal appears.
   if(nhBar >= 0)
      FillSeg(bufNearHigh, nhBar, nhPrc, rates_total - 1, nhPrc);
   if(nlBar >= 0)
      FillSeg(bufNearLow, nlBar, nlPrc, rates_total - 1, nlPrc);

   //--- breakout: check the remaining bars against the active levels, then draw the latest event only
   ScanBreaks(scanned + 1, rates_total - 1, high, low, close);
   DrawBreak(rates_total);

   return(rates_total);
  }
//+------------------------------------------------------------------+