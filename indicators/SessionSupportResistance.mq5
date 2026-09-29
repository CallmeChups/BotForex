#property copyright "BotForex"
#property version   "1.0"
#property description "Support va resistance theo tung phien giao dich."
#property description "Moi muc duoc tinh tu High/Low cua mot phien."
#property description "Gia hien hanh vuot muc se danh dau phu dinh."
#property indicator_chart_window
#property indicator_plots   0

input group "Cau hinh 7 phien (gio theo server MT5)"
input int Phien1_BatDau = 20;
input int Phien2_BatDau = 0;
input int Phien3_BatDau = 5;
input int Phien4_BatDau = 8;
input int Phien5_BatDau = 11;
input int Phien6_BatDau = 14;
input int Phien7_BatDau = 18;

input group "Hien thi"
input color MauResistance = clrTomato;
input color MauSupport = clrDeepSkyBlue;
input int DoRongDuong = 1;
input ENUM_LINE_STYLE KieuDuong = STYLE_SOLID;
input bool HienThiNhanPhien = true;
input color MauNhanPhien = clrDimGray;
input int CoChuNhanPhien = 8;
input int SoPhienHienThi = 7;

struct SessionInfo
  {
   datetime start;
   datetime finish;
   double high;
   double low;
   int slot;
   bool has_data;
   bool resistance_broken;
   bool support_broken;
   bool is_current;
  };

string Prefix = "SessionSR_";
int SessionStarts[7];
SessionInfo Sessions[];

int OnInit()
  {
   SessionStarts[0] = Phien1_BatDau;
   SessionStarts[1] = Phien2_BatDau;
   SessionStarts[2] = Phien3_BatDau;
   SessionStarts[3] = Phien4_BatDau;
   SessionStarts[4] = Phien5_BatDau;
   SessionStarts[5] = Phien6_BatDau;
   SessionStarts[6] = Phien7_BatDau;

   for(int i = 0; i < 7; i++)
      if(SessionStarts[i] < 0 || SessionStarts[i] > 23)
         return(INIT_PARAMETERS_INCORRECT);

   XoaDoiTuong();
   IndicatorSetString(INDICATOR_SHORTNAME, "Session Support Resistance");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   XoaDoiTuong();
   ChartRedraw(0);
  }

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
   if(rates_total < 2)
      return(0);

   ArraySetAsSeries(time, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);

   ArrayResize(Sessions, 0);
   XoaDoiTuong();
   XayDungPhien(rates_total, time, high, low);

   datetime now = TimeCurrent();
   int current = TimPhien(now);
   double current_price = GiaHienHanh(close[0]);
   if(current >= 0)
      DanhDauPhuDinh(current, current_price);

   VeCacMuc();
   ChartRedraw(0);
   return(rates_total);
  }

void XayDungPhien(const int rates_total,
                  const datetime &time[],
                  const double &high[],
                  const double &low[])
  {
   // Series arrays are walked from oldest to newest so each session is complete.
   for(int index = rates_total - 1; index >= 0; index--)
     {
      int slot = -1;
      datetime start = BatDauPhien(time[index], slot);
      if(start <= 0)
         continue;

      int count = ArraySize(Sessions);
      if(count == 0 || Sessions[count - 1].start != start)
        {
         SessionInfo item;
         item.start = start;
         item.finish = KetThucPhien(start, slot);
         item.high = high[index];
         item.low = low[index];
         item.slot = slot;
         item.has_data = true;
         item.resistance_broken = false;
         item.support_broken = false;
         item.is_current = false;
         ArrayResize(Sessions, count + 1);
         Sessions[count] = item;
        }
      else
        {
         if(high[index] > Sessions[count - 1].high)
            Sessions[count - 1].high = high[index];
         if(low[index] < Sessions[count - 1].low)
            Sessions[count - 1].low = low[index];
        }
     }

   datetime now = TimeCurrent();
   for(int i = 0; i < ArraySize(Sessions); i++)
      Sessions[i].is_current = now >= Sessions[i].start &&
                               now <= Sessions[i].finish;

   // A session invalidates the levels of its immediately preceding session.
   for(int i = 1; i < ArraySize(Sessions); i++)
     {
      if(!Sessions[i].is_current)
        {
         if(Sessions[i].high > Sessions[i - 1].high)
            Sessions[i - 1].resistance_broken = true;
         if(Sessions[i].low < Sessions[i - 1].low)
            Sessions[i - 1].support_broken = true;
        }
     }
  }

datetime BatDauPhien(const datetime value, int &slot)
  {
   MqlDateTime parts;
   TimeToStruct(value, parts);
   slot = -1;
   int selected_hour = -1;

   for(int i = 0; i < 7; i++)
     {
      if(SessionStarts[i] <= parts.hour && SessionStarts[i] > selected_hour)
        {
         selected_hour = SessionStarts[i];
         slot = i;
        }
     }

   MqlDateTime start_parts = parts;
   if(slot < 0)
     {
      slot = 0;
      start_parts.day--;
     }
   start_parts.hour = SessionStarts[slot];
   start_parts.min = 0;
   start_parts.sec = 0;
   return(StructToTime(start_parts));
  }

datetime KetThucPhien(const datetime start, const int slot)
  {
   int next_slot = (slot + 1) % 7;
   MqlDateTime next_parts;
   TimeToStruct(start, next_parts);
   if(next_slot == 0)
      next_parts.day++;
   next_parts.hour = SessionStarts[next_slot];
   next_parts.min = 0;
   next_parts.sec = 0;
   return(StructToTime(next_parts) - 1);
  }

int TimPhien(const datetime value)
  {
   for(int i = 0; i < ArraySize(Sessions); i++)
      if(value >= Sessions[i].start && value <= Sessions[i].finish)
         return(i);
   return(-1);
  }

double GiaHienHanh(const double fallback)
  {
   MqlTick tick;
   if(SymbolInfoTick(_Symbol, tick))
     {
      if(tick.bid > 0.0)
         return(tick.bid);
      if(tick.last > 0.0)
         return(tick.last);
     }
   return(fallback);
  }

void DanhDauPhuDinh(const int current, const double price)
  {
   if(current <= 0 || current >= ArraySize(Sessions))
      return;

   int previous = current - 1;
   if(price > Sessions[previous].high)
      Sessions[previous].resistance_broken = true;
   if(price < Sessions[previous].low)
      Sessions[previous].support_broken = true;
  }

void VeCacMuc()
  {
   int so_phien = MathMax(1, SoPhienHienThi);
   int phien_dau = TimPhienDauCanHienThi(so_phien);
   if(phien_dau < 0)
      return;

   for(int i = 0; i < ArraySize(Sessions); i++)
     {
      if(i < phien_dau)
         continue;
      if(!Sessions[i].has_data)
         continue;

      if(!Sessions[i].resistance_broken ||
         (i + 1 < ArraySize(Sessions) && Sessions[i + 1].is_current))
         VeMuc("R", i, Sessions[i].high, MauResistance);
      if(!Sessions[i].support_broken ||
         (i + 1 < ArraySize(Sessions) && Sessions[i + 1].is_current))
         VeMuc("S", i, Sessions[i].low, MauSupport);
     }
  }

int TimPhienDauCanHienThi(const int so_phien)
  {
   int da_dem = 0;
   for(int i = ArraySize(Sessions) - 1; i >= 0; i--)
     {
      if(!Sessions[i].has_data)
         continue;

      bool con_cac = !Sessions[i].resistance_broken ||
                     !Sessions[i].support_broken;
      if(!con_cac)
         continue;

      da_dem++;
      if(da_dem >= so_phien)
         return(i);
     }
   return(0);
  }

void VeMuc(const string type,
           const int index,
           const double price,
           const color line_color)
  {
   datetime finish = TimeCurrent();
   if(finish <= Sessions[index].start)
      return;

   string name = Prefix + type + "_" + IntegerToString(index);
   if(!ObjectCreate(0, name, OBJ_TREND, 0, Sessions[index].start, price,
                    finish, price))
      return;
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_COLOR, line_color);
   ObjectSetInteger(0, name, OBJPROP_STYLE, KieuDuong);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, MathMax(1, DoRongDuong));
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);

   if(HienThiNhanPhien)
     {
      string label_name = Prefix + "Label_" + type + "_" +
                          IntegerToString(index);
      string label_text = IntegerToString(SessionStarts[Sessions[index].slot]) +
                          ":00 " + type;
      if(ObjectCreate(0, label_name, OBJ_TEXT, 0, Sessions[index].start, price))
        {
         ObjectSetString(0, label_name, OBJPROP_TEXT, label_text);
         ObjectSetString(0, label_name, OBJPROP_FONT, "Arial");
         ObjectSetInteger(0, label_name, OBJPROP_FONTSIZE,
                          MathMax(6, CoChuNhanPhien));
         ObjectSetInteger(0, label_name, OBJPROP_COLOR, MauNhanPhien);
         ObjectSetInteger(0, label_name, OBJPROP_ANCHOR, ANCHOR_LEFT);
         ObjectSetInteger(0, label_name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, label_name, OBJPROP_HIDDEN, true);
        }
     }
  }

void XoaDoiTuong()
  {
   ObjectsDeleteAll(0, Prefix);
  }
