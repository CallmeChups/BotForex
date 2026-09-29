#property copyright "BotForex"
#property version   "1.0"
#property description "Chỉ báo đỉnh đáy cho MetaTrader 5."
#property description "Chọn kiểu trong tab Inputs rồi chỉnh nhóm tương ứng."
#property description "Đường nối: lọc swing lớn bằng độ sâu và ATR."
#property description "Nến mẫu: xác nhận theo các nến xung quanh."
#property description "Tùy chỉnh: lọc theo số nến và khoảng cách."
#property description "Swing gần giá hiện tại cần đủ nến để xác nhận."
#property description "Hiển thị swing bằng chấm màu; đường nối là tùy chọn."
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots   2

#property indicator_label1  "Đỉnh"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrTomato
#property indicator_width1  2
#property indicator_label2  "Đáy"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrDeepSkyBlue
#property indicator_width2  2

enum ENUM_KIEU_XAC_DINH
  {
   KIEU_DUONG_NOI = 0,       // Đường nối đỉnh đáy
   KIEU_NEN_MAU = 1,         // Đỉnh đáy theo nến mẫu
   KIEU_TUY_CHINH = 2        // Đỉnh đáy theo điều kiện tùy chỉnh
  };

input group "Cài đặt chung - chọn kiểu và cách hiển thị"
input ENUM_KIEU_XAC_DINH KieuXacDinh = KIEU_TUY_CHINH; // Chọn một kiểu xác định đỉnh đáy
input bool HienThiDuongNoi = true;                     // Nối các swing bằng đường
input color MauDinh = clrTomato;                        // Màu đỉnh
input color MauDay = clrDeepSkyBlue;                    // Màu đáy
input color MauDuongNoi = clrSilver;                    // Màu đường nối
input int DoRongDuong = 1;                              // Độ rộng đường nối

input group "Cấu hình đường nối đỉnh đáy - phù hợp để lọc swing lớn"
input int DuongNoi_DoSau = 12;                          // Số nến tối thiểu của một swing
input double DuongNoi_DaoChieuToiThieu = 0.0;           // Đảo chiều tối thiểu (point), 0 = dùng ATR
input int DuongNoi_ChieuDaiATR = 14;                    // Chiều dài ATR khi tự động lọc
input double DuongNoi_HeSoATR = 1.0;                    // Hệ số ATR khi tự động lọc

input group "Cấu hình nến mẫu - xác nhận theo các nến xung quanh"
input int NenMau_SoNenBenTrai = 2;                      // Số nến phía bên trái
input int NenMau_SoNenBenPhai = 2;                      // Số nến phía bên phải
input double NenMau_KhoangCachToiThieu = 0.0;           // Khoảng cách giá tối thiểu (point)

input group "Cấu hình tùy chỉnh - kiểm soát chi tiết độ lọc"
input int TuyChinh_SoNenBenTrai = 3;                    // Số nến phía bên trái
input int TuyChinh_SoNenBenPhai = 3;                    // Số nến phía bên phải
input double TuyChinh_KhoangCachToiThieu = 0.0;         // Khoảng cách giá tối thiểu (point)
input int TuyChinh_SoNenToiThieu = 3;                   // Số nến tối thiểu giữa hai điểm
input bool TuyChinh_LocTheoATR = false;                 // Lọc thêm theo độ biến động ATR
input int TuyChinh_ChuKyATR = 14;                       // Chu kỳ ATR
input double TuyChinh_HeSoATR = 1.0;                    // Hệ số ATR

double DinhBuffer[];
double DayBuffer[];
double LoaiSwingBuffer[];
double GiaSwingBuffer[];
string TienTo = "SwingStructureMaster_";

int OnInit()
  {
   XoaDoiTuong();
   SetIndexBuffer(0, DinhBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, DayBuffer, INDICATOR_DATA);
   SetIndexBuffer(2, LoaiSwingBuffer, INDICATOR_CALCULATIONS);
   SetIndexBuffer(3, GiaSwingBuffer, INDICATOR_CALCULATIONS);
   ArraySetAsSeries(DinhBuffer, true);
   ArraySetAsSeries(DayBuffer, true);
   ArraySetAsSeries(LoaiSwingBuffer, true);
   ArraySetAsSeries(GiaSwingBuffer, true);
   PlotIndexSetInteger(0, PLOT_ARROW, 159);
   PlotIndexSetInteger(1, PLOT_ARROW, 159);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   IndicatorSetString(INDICATOR_SHORTNAME, "Swing Structure Master - Đỉnh Đáy");
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
   ArraySetAsSeries(time, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);
   int doSau = MathMax(1, MathMax(DuongNoi_DoSau, MathMax(NenMau_SoNenBenTrai, TuyChinh_SoNenBenTrai)));
   int benPhai = MathMax(1, MathMax(NenMau_SoNenBenPhai, TuyChinh_SoNenBenPhai));
   if(rates_total <= doSau + benPhai + 3)
      return(0);

   bool canVeLai = prev_calculated == 0 || prev_calculated < rates_total;
   if(!canVeLai)
      return(rates_total);

   bool veToanBo = prev_calculated == 0;
   ArrayInitialize(DinhBuffer, EMPTY_VALUE);
   ArrayInitialize(DayBuffer, EMPTY_VALUE);
   ArrayInitialize(LoaiSwingBuffer, 0.0);
   ArrayInitialize(GiaSwingBuffer, 0.0);
   if(veToanBo)
     {
      XoaDoiTuong();
     }
   else
     {
      int vung = MathMin(rates_total - 1, MathMax(30, doSau + benPhai + 10));
      XoaDoiTuongGan(time[vung]);
      for(int i = 0; i <= vung; i++)
        {
         DinhBuffer[i] = EMPTY_VALUE;
         DayBuffer[i] = EMPTY_VALUE;
         LoaiSwingBuffer[i] = 0.0;
         GiaSwingBuffer[i] = 0.0;
        }
     }

   if(KieuXacDinh == KIEU_DUONG_NOI)
      TinhDuongNoi(rates_total, time, high, low, close);
   else if(KieuXacDinh == KIEU_NEN_MAU)
      TinhNenMau(rates_total, time, high, low);
   else
      TinhTuyChinh(rates_total, time, high, low, close);

   if(veToanBo)
      VeKetQua(rates_total, time, high, low);
   else
      VeKetQuaVung(rates_total, time, doSau, benPhai);
   ChartRedraw(0);
   return(rates_total);
  }

void TinhNenMau(const int tong,
                const datetime &time[],
                const double &high[],
                const double &low[])
  {
   int trai = MathMax(1, NenMau_SoNenBenTrai);
   int phai = MathMax(1, NenMau_SoNenBenPhai);
   for(int i = tong - trai - 1; i > phai; i--)
     {
      bool laDinh = true;
      bool laDay = true;
      for(int j = 1; j <= trai; j++)
        {
         if(high[i] <= high[i + j])
            laDinh = false;
         if(low[i] >= low[i + j])
            laDay = false;
        }
      if(laDinh || laDay)
        {
         for(int j = 1; j <= phai; j++)
           {
            if(high[i] <= high[i - j])
               laDinh = false;
            if(low[i] >= low[i - j])
               laDay = false;
           }
         if(laDinh || laDay)
            GhiSwing(i, laDinh, laDay, high, low, NenMau_KhoangCachToiThieu, 0);
        }
     }
  }

void TinhTuyChinh(const int tong,
                  const datetime &time[],
                  const double &high[],
                  const double &low[],
                  const double &close[])
  {
   int trai = MathMax(1, TuyChinh_SoNenBenTrai);
   int phai = MathMax(1, TuyChinh_SoNenBenPhai);
   for(int i = tong - trai - 1; i > phai; i--)
     {
      bool laDinh = true;
      bool laDay = true;
      for(int j = 1; j <= trai; j++)
        {
         if(high[i] <= high[i + j])
            laDinh = false;
         if(low[i] >= low[i + j])
            laDay = false;
        }
      for(int j = 1; j <= phai; j++)
        {
         if(high[i] <= high[i - j])
            laDinh = false;
         if(low[i] >= low[i - j])
            laDay = false;
        }
      double khoangCach = TuyChinh_KhoangCachToiThieu;
      if(TuyChinh_LocTheoATR)
         khoangCach = MathMax(khoangCach, TinhATR(tong, i, TuyChinh_ChuKyATR,
                                                   high, low, close) * TuyChinh_HeSoATR / _Point);
      GhiSwing(i, laDinh, laDay, high, low, khoangCach, TuyChinh_SoNenToiThieu);
     }
  }

void TinhDuongNoi(const int tong,
                  const datetime &time[],
                  const double &high[],
                  const double &low[],
                  const double &close[])
  {
   int sau = MathMax(1, DuongNoi_DoSau);
   for(int i = tong - sau - 1; i > sau; i--)
     {
      bool laDinh = true;
      bool laDay = true;
      for(int j = 1; j <= sau; j++)
        {
         if(high[i] <= high[i + j] || high[i] <= high[i - j])
            laDinh = false;
         if(low[i] >= low[i + j] || low[i] >= low[i - j])
            laDay = false;
        }
      double khoangCach = DuongNoi_DaoChieuToiThieu;
      if(khoangCach <= 0.0)
         khoangCach = TinhATR(tong, i, DuongNoi_ChieuDaiATR, high, low, close)
                      * DuongNoi_HeSoATR / _Point;
      GhiSwing(i, laDinh, laDay, high, low, khoangCach, 0);
     }
  }

void GhiSwing(const int i,
              const bool laDinh,
              const bool laDay,
              const double &high[],
              const double &low[],
              const double khoangCachPoint,
              const int khoangCachNen)
  {
   if(!laDinh && !laDay)
      return;
   if(laDinh && laDay)
      return;
   double nguong = MathMax(0.0, khoangCachPoint) * _Point;
   if(laDinh)
     {
   if(CoSwingGanNhat(true, i, high[i], nguong, khoangCachNen))
         return;
      DinhBuffer[i] = high[i];
      LoaiSwingBuffer[i] = 1.0;
      GiaSwingBuffer[i] = high[i];
     }
   if(laDay)
     {
      if(CoSwingGanNhat(false, i, low[i], nguong, khoangCachNen))
         return;
      DayBuffer[i] = low[i];
      LoaiSwingBuffer[i] = -1.0;
      GiaSwingBuffer[i] = low[i];
     }
  }

bool CoSwingGanNhat(const bool laDinh,
                    const int i,
                    const double gia,
                    const double nguong,
                    const int khoangCachNen)
  {
   int batDau = i + 1;
   int ketThuc = ArraySize(LoaiSwingBuffer) - 1;
   for(int j = batDau; j <= ketThuc; j++)
     {
      if(laDinh && LoaiSwingBuffer[j] == 1.0)
         return(j - i < khoangCachNen ||
                MathAbs(gia - GiaSwingBuffer[j]) < nguong);
      if(!laDinh && LoaiSwingBuffer[j] == -1.0)
         return(j - i < khoangCachNen ||
                MathAbs(gia - GiaSwingBuffer[j]) < nguong);
     }
   return(false);
  }

double TinhATR(const int tong,
               const int viTri,
               const int chuKy,
               const double &high[],
               const double &low[],
               const double &close[])
  {
   int n = MathMax(1, chuKy);
   double tongTR = 0.0;
   int dem = 0;
   for(int i = viTri; i < MathMin(tong - 1, viTri + n); i++)
     {
      double truoc = close[i + 1];
      double tr = MathMax(high[i] - low[i],
                          MathMax(MathAbs(high[i] - truoc), MathAbs(low[i] - truoc)));
      tongTR += tr;
      dem++;
     }
   return(dem > 0 ? tongTR / dem : 0.0);
  }

void VeKetQua(const int tong,
              const datetime &time[],
              const double &high[],
              const double &low[])
  {
   int swingTruoc = -1;
   double dinhTruoc = 0.0;
   double dayTruoc = 0.0;
   for(int i = tong - 1; i >= 0; i--)
     {
      if(LoaiSwingBuffer[i] == 0.0)
         continue;
      bool laDinh = LoaiSwingBuffer[i] > 0.0;
      double gia = GiaSwingBuffer[i];
      if(laDinh)
         dinhTruoc = gia;
      else
         dayTruoc = gia;
      if(HienThiDuongNoi && swingTruoc >= 0)
         TaoDuong(swingTruoc, i, time[swingTruoc], GiaSwingBuffer[swingTruoc],
                  time[i], gia);
      swingTruoc = i;
     }
  }

void VeKetQuaVung(const int tong,
                  const datetime &time[],
                  const int doSau,
                  const int benPhai)
  {
   int batDau = MathMin(tong - 1, MathMax(30, doSau + benPhai + 10));
   int swingTruoc = -1;
   double dinhTruoc = 0.0;
   double dayTruoc = 0.0;
   for(int j = batDau + 1; j < tong; j++)
     {
      if(LoaiSwingBuffer[j] == 0.0)
         continue;
      if(swingTruoc < 0)
         swingTruoc = j;
      if(LoaiSwingBuffer[j] > 0.0 && dinhTruoc == 0.0)
         dinhTruoc = GiaSwingBuffer[j];
      if(LoaiSwingBuffer[j] < 0.0 && dayTruoc == 0.0)
         dayTruoc = GiaSwingBuffer[j];
      if(swingTruoc >= 0 && dinhTruoc != 0.0 && dayTruoc != 0.0)
         break;
     }
   for(int i = batDau; i >= 0; i--)
     {
      if(LoaiSwingBuffer[i] == 0.0)
         continue;
      bool laDinh = LoaiSwingBuffer[i] > 0.0;
      double gia = GiaSwingBuffer[i];
      if(laDinh)
         dinhTruoc = gia;
      else
         dayTruoc = gia;
      if(HienThiDuongNoi && swingTruoc >= 0)
         TaoDuong(swingTruoc, i, time[swingTruoc], GiaSwingBuffer[swingTruoc],
                  time[i], gia);
      swingTruoc = i;
     }
  }

void TaoDuong(const int diemCu,
              const int diemMoi,
              const datetime thoiGianCu,
              const double giaCu,
              const datetime thoiGianMoi,
              const double giaMoi)
  {
   string ten = TienTo + "Duong_" + IntegerToString((int)thoiGianCu) + "_" +
                IntegerToString((int)thoiGianMoi);
   ObjectDelete(0, ten);
   ObjectCreate(0, ten, OBJ_TREND, 0, thoiGianCu, giaCu, thoiGianMoi, giaMoi);
   ObjectSetInteger(0, ten, OBJPROP_COLOR, MauDuongNoi);
   ObjectSetInteger(0, ten, OBJPROP_WIDTH, DoRongDuong);
   ObjectSetInteger(0, ten, OBJPROP_RAY_RIGHT, false);
  }

void XoaDoiTuong()
  {
   ObjectsDeleteAll(0, TienTo);
  }

void XoaDoiTuongGan(const datetime mocThoiGian)
  {
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string ten = ObjectName(0, i, 0, -1);
      if(StringFind(ten, TienTo) < 0)
         continue;
      datetime thoiGian0 = (datetime)ObjectGetInteger(0, ten, OBJPROP_TIME, 0);
      datetime thoiGian1 = (datetime)ObjectGetInteger(0, ten, OBJPROP_TIME, 1);
      if(thoiGian0 >= mocThoiGian || (thoiGian1 > 0 && thoiGian1 >= mocThoiGian))
         ObjectDelete(0, ten);
     }
  }
