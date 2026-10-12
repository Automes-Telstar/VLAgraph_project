/PROG  S05PROC
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "9QBC F50mm R90mm";
PROG_SIZE	= 5394;
CREATE		= DATE 21-09-06  TIME 11:15:48;
MODIFIED	= DATE 23-02-15  TIME 15:03:34;
FILE_NAME	= S01PROC;
VERSION		= 0;
LINE_COUNT	= 123;
MEMORY_SIZE	= 5658;
PROTECT		= READ_WRITE;
TCD:  STACK_SIZE	= 0,
      TASK_PRIORITY	= 50,
      TIME_SLICE	= 0,
      BUSY_LAMP_OFF	= 0,
      ABORT_REQUEST	= 0,
      PAUSE_REQUEST	= 0;
DEFAULT_GROUP	= 1,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
/APPL
  SPOT Welding Equipment Number : 1 ;
/MN
   1:  SET SEGMENT(10) ;
   2:   ;
   3:  UFRAME_NUM=1 ;
   4:  UTOOL_NUM=1 ;
   5:  PAYLOAD[1] ;
   6:   ;
   7:  ENTER I-ZONE(5) ;
   8:  ENTER I-ZONE(6) ;
   9:   ;
  10:J P[1:POUNCE] 30% FINE    ;
  11:   ;
  12:  !Front Door Full Open ;
  13:J P[46] 30% CNT100    ;
  14:L P[3] 400mm/sec CNT100    ;
  15:L P[6] 400mm/sec CNT50    ;
  16:L P[7] 250mm/sec CNT100    ;
  17:L P[8] 150mm/sec FINE    ;
  18:  WAIT    .30(sec) ;
  19:L P[9] 150mm/sec FINE    ;
  20:L P[10] 250mm/sec CNT100    ;
  21:L P[11] 250mm/sec CNT100    ;
  22:L P[12] 250mm/sec CNT100    ;
  23:L P[13] 250mm/sec CNT100    ;
  24:L P[15] 250mm/sec CNT100    ;
  25:L P[16] 250mm/sec CNT100    ;
  26:L P[48] 250mm/sec CNT100    ;
  27:L P[50] 250mm/sec CNT100    ;
  28:L P[51] 250mm/sec CNT100    ;
  29:L P[17:END] 250mm/sec FINE    ;
  30:   ;
  31:  !@@ WAIT Stopper On @@ ;
  32:  ENTER PLC ZONE(1) ;
  33:  WAIT   1.00(sec) ;
  34:   ;
  35:  !Front Door -) Rear Door ;
  36:L P[18] 250mm/sec FINE    ;
  37:L P[14] 400mm/sec CNT50    ;
  38:J P[19] 80% CNT100    ;
  39:J P[20] 80% CNT100    ;
  40:J P[21] 80% CNT100    ;
  41:J P[22] 80% CNT100    ;
  42:J P[23] 80% CNT100    ;
  43:J P[24] 80% CNT100    ;
  44:J P[52] 80% CNT100    ;
  45:   ;
  46:  !Rear Door Open ;
  47:L P[25] 400mm/sec CNT100    ;
  48:L P[27] 400mm/sec CNT50    ;
  49:L P[62] 250mm/sec CNT50    ;
  50:L P[28] 150mm/sec FINE    ;
  51:  WAIT    .30(sec) ;
  52:L P[29] 150mm/sec CNT100    ;
  53:L P[49] 150mm/sec CNT100    ;
  54:L P[53] 50mm/sec FINE    ;
  55:   ;
  56:  EXIT I-ZONE(5) ;
  57:   ;
  58:  !@@ WAIT R1 DO[602]-ON @@ ;
  59:  ENTER PLC ZONE(2) ;
  60:  SET SEGMENT(30) ;
  61:   ;
  62:  ENTER I-ZONE(5) ;
  63:  ENTER I-ZONE(6) ;
  64:   ;
  65:  !Reer Door Close ;
  66:L P[47] 150mm/sec FINE    ;
  67:L P[30] 150mm/sec FINE    ;
  68:  WAIT    .30(sec) ;
  69:L P[26] 150mm/sec FINE    ;
  70:L P[5] 250mm/sec CNT50    ;
  71:L P[4] 400mm/sec CNT50    ;
  72:L P[2] 400mm/sec CNT100    ;
  73:   ;
  74:  !Rear Door -) Front Door ;
  75:J P[57] 80% CNT100    ;
  76:J P[56] 80% CNT100    ;
  77:J P[37] 80% CNT100    ;
  78:J P[36] 80% CNT100    ;
  79:J P[35] 80% CNT100    ;
  80:J P[34] 80% CNT100    ;
  81:J P[33] 80% CNT100    ;
  82:L P[32] 400mm/sec CNT50    ;
  83:L P[31] 250mm/sec FINE    ;
  84:   ;
  85:  !@@ WAIT Stopper Off @@ ;
  86:  WAIT   1.00(sec) ;
  87:  ENTER PLC ZONE(3) ;
  88:  WAIT   1.00(sec) ;
  89:   ;
  90:  !Front Door 1st Close ;
  91:L P[73:END] 250mm/sec FINE    ;
  92:L P[72] 250mm/sec CNT100    ;
  93:L P[71] 250mm/sec CNT100    ;
  94:L P[70] 250mm/sec CNT100    ;
  95:L P[69] 250mm/sec CNT100    ;
  96:L P[68] 250mm/sec CNT100    ;
  97:L P[67] 250mm/sec CNT100    ;
  98:L P[66] 250mm/sec CNT100    ;
  99:L P[65] 250mm/sec CNT100    ;
 100:L P[64] 250mm/sec FINE    ;
 101:   ;
 102:  EXIT I-ZONE(6) ;
 103:   ;
 104:  !@@ WAIT R3 DO[603]-ON @@ ;
 105:  ENTER PLC ZONE(4) ;
 106:   ;
 107:  ENTER I-ZONE(5) ;
 108:  ENTER I-ZONE(6) ;
 109:   ;
 110:  !Front Door 2nd Close ;
 111:L P[44] 150mm/sec FINE    ;
 112:L P[38] 150mm/sec FINE    ;
 113:  WAIT    .30(sec) ;
 114:L P[39] 150mm/sec FINE    ;
 115:L P[40] 250mm/sec CNT100    ;
 116:L P[41] 400mm/sec CNT50    ;
 117:L P[42] 400mm/sec CNT100    ;
 118:J P[43] 30% CNT100    ;
 119:   ;
 120:J P[45:POUNCE] 30% FINE    ;
 121:   ;
 122:  EXIT I-ZONE(5) ;
 123:  EXIT I-ZONE(6) ;
/POS
P[1:"POUNCE"]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2809.061  mm,	Y =  -998.344  mm,	Z =  1571.460  mm,
	W =  -176.294 deg,	P =     -.116 deg,	R =   -90.092 deg
};
P[2]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3741.473  mm,	Y =  -668.276  mm,	Z =  1653.188  mm,
	W =  -178.816 deg,	P =    -8.105 deg,	R =   -88.015 deg
};
P[3]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2947.474  mm,	Y =  -690.446  mm,	Z =  1595.549  mm,
	W =  -176.294 deg,	P =     -.116 deg,	R =   -90.092 deg
};
P[4:""]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3745.724  mm,	Y =  -687.246  mm,	Z =  1621.172  mm,
	W =  -178.816 deg,	P =    -8.106 deg,	R =   -88.015 deg
};
P[5]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3748.636  mm,	Y =  -711.451  mm,	Z =  1522.827  mm,
	W =  -178.817 deg,	P =    -8.104 deg,	R =   -88.017 deg
};
P[6]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.558  mm,	Y =  -712.967  mm,	Z =  1504.916  mm,
	W =  -176.294 deg,	P =     -.116 deg,	R =   -90.092 deg
};
P[7]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.555  mm,	Y =  -715.127  mm,	Z =  1504.920  mm,
	W =  -176.294 deg,	P =     -.116 deg,	R =   -90.092 deg
};
P[8]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.544  mm,	Y =  -721.607  mm,	Z =  1504.933  mm,
	W =  -176.294 deg,	P =     -.117 deg,	R =   -90.092 deg
};
P[9]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.540  mm,	Y =  -724.308  mm,	Z =  1504.938  mm,
	W =  -176.292 deg,	P =     -.067 deg,	R =   -90.860 deg
};
P[10]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.394  mm,	Y =  -751.142  mm,	Z =  1499.232  mm,
	W =  -176.293 deg,	P =      .079 deg,	R =   -93.059 deg
};
P[11]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2954.146  mm,	Y =  -793.202  mm,	Z =  1499.174  mm,
	W =  -176.303 deg,	P =      .290 deg,	R =   -96.319 deg
};
P[12]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2948.809  mm,	Y =  -839.711  mm,	Z =  1501.811  mm,
	W =  -176.337 deg,	P =      .578 deg,	R =  -100.798 deg
};
P[13]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2937.781  mm,	Y =  -895.569  mm,	Z =  1506.984  mm,
	W =  -176.395 deg,	P =      .867 deg,	R =  -105.343 deg
};
P[14]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2773.908  mm,	Y = -1193.153  mm,	Z =  1662.672  mm,
	W =  -177.432 deg,	P =     2.674 deg,	R =  -137.989 deg
};
P[15]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2922.458  mm,	Y =  -949.707  mm,	Z =  1513.319  mm,
	W =  -176.486 deg,	P =     1.183 deg,	R =  -110.416 deg
};
P[16]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2898.984  mm,	Y = -1011.761  mm,	Z =  1517.701  mm,
	W =  -176.618 deg,	P =     1.520 deg,	R =  -116.017 deg
};
P[17:"END"]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2769.980  mm,	Y = -1204.246  mm,	Z =  1536.899  mm,
	W =  -177.432 deg,	P =     2.674 deg,	R =  -137.989 deg
};
P[18]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2769.980  mm,	Y = -1204.246  mm,	Z =  1536.899  mm,
	W =  -177.432 deg,	P =     2.674 deg,	R =  -137.989 deg
};
P[19]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2469.626  mm,	Y = -1359.404  mm,	Z =  1674.604  mm,
	W =   133.903 deg,	P =    -5.276 deg,	R =  -144.932 deg
};
P[20]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2542.929  mm,	Y = -1725.231  mm,	Z =  1637.415  mm,
	W =   149.499 deg,	P =    -4.870 deg,	R =  -111.383 deg
};
P[21]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2888.370  mm,	Y = -1891.178  mm,	Z =  1626.037  mm,
	W =   175.652 deg,	P =    -3.434 deg,	R =   -88.133 deg
};
P[22]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3254.893  mm,	Y = -1786.740  mm,	Z =  1592.332  mm,
	W =   175.395 deg,	P =    -3.080 deg,	R =   -83.602 deg
};
P[23]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3533.247  mm,	Y = -1468.324  mm,	Z =  1551.795  mm,
	W =   175.395 deg,	P =    -3.080 deg,	R =   -83.603 deg
};
P[24]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3669.018  mm,	Y =  -828.777  mm,	Z =  1731.953  mm,
	W =   142.308 deg,	P =    -5.320 deg,	R =   -89.000 deg
};
P[25]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3741.473  mm,	Y =  -668.276  mm,	Z =  1653.188  mm,
	W =  -178.816 deg,	P =    -8.105 deg,	R =   -88.015 deg
};
P[26]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3749.180  mm,	Y =  -720.712  mm,	Z =  1513.242  mm,
	W =  -178.817 deg,	P =    -8.104 deg,	R =   -88.017 deg
};
P[27:""]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3745.724  mm,	Y =  -687.246  mm,	Z =  1621.172  mm,
	W =  -178.816 deg,	P =    -8.106 deg,	R =   -88.015 deg
};
P[28]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3749.180  mm,	Y =  -720.712  mm,	Z =  1513.242  mm,
	W =  -178.817 deg,	P =    -8.104 deg,	R =   -88.017 deg
};
P[29]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3749.487  mm,	Y =  -725.994  mm,	Z =  1507.936  mm,
	W =  -178.817 deg,	P =    -8.105 deg,	R =   -88.017 deg
};
P[30]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3749.487  mm,	Y =  -725.994  mm,	Z =  1507.936  mm,
	W =  -178.817 deg,	P =    -8.105 deg,	R =   -88.017 deg
};
P[31]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2769.980  mm,	Y = -1204.246  mm,	Z =  1536.899  mm,
	W =  -177.432 deg,	P =     2.674 deg,	R =  -137.989 deg
};
P[32]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2773.908  mm,	Y = -1193.152  mm,	Z =  1662.672  mm,
	W =  -177.432 deg,	P =     2.674 deg,	R =  -137.989 deg
};
P[33]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2469.626  mm,	Y = -1359.404  mm,	Z =  1674.604  mm,
	W =   133.903 deg,	P =    -5.276 deg,	R =  -144.932 deg
};
P[34]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2542.929  mm,	Y = -1725.231  mm,	Z =  1637.415  mm,
	W =   149.499 deg,	P =    -4.870 deg,	R =  -111.383 deg
};
P[35]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2888.370  mm,	Y = -1891.178  mm,	Z =  1626.037  mm,
	W =   175.652 deg,	P =    -3.434 deg,	R =   -88.133 deg
};
P[36]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3254.893  mm,	Y = -1786.740  mm,	Z =  1592.332  mm,
	W =   175.395 deg,	P =    -3.080 deg,	R =   -83.602 deg
};
P[37]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3533.247  mm,	Y = -1468.324  mm,	Z =  1551.795  mm,
	W =   175.395 deg,	P =    -3.080 deg,	R =   -83.603 deg
};
P[38]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.540  mm,	Y =  -724.308  mm,	Z =  1504.938  mm,
	W =  -176.292 deg,	P =     -.067 deg,	R =   -90.860 deg
};
P[39]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.544  mm,	Y =  -721.607  mm,	Z =  1504.933  mm,
	W =  -176.294 deg,	P =     -.117 deg,	R =   -90.092 deg
};
P[40]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.555  mm,	Y =  -715.127  mm,	Z =  1504.920  mm,
	W =  -176.294 deg,	P =     -.116 deg,	R =   -90.092 deg
};
P[41]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.558  mm,	Y =  -712.967  mm,	Z =  1504.916  mm,
	W =  -176.294 deg,	P =     -.116 deg,	R =   -90.092 deg
};
P[42]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2947.474  mm,	Y =  -690.446  mm,	Z =  1595.549  mm,
	W =  -176.294 deg,	P =     -.116 deg,	R =   -90.092 deg
};
P[43]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2941.912  mm,	Y =  -705.383  mm,	Z =  1681.080  mm,
	W =  -176.294 deg,	P =     -.116 deg,	R =   -90.092 deg
};
P[44]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.394  mm,	Y =  -751.142  mm,	Z =  1499.232  mm,
	W =  -176.293 deg,	P =      .078 deg,	R =   -93.059 deg
};
P[45:"POUNCE"]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2809.061  mm,	Y =  -998.344  mm,	Z =  1571.460  mm,
	W =  -176.294 deg,	P =     -.116 deg,	R =   -90.092 deg
};
P[46]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2941.912  mm,	Y =  -705.383  mm,	Z =  1681.080  mm,
	W =  -176.294 deg,	P =     -.116 deg,	R =   -90.092 deg
};
P[47]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3749.652  mm,	Y =  -749.300  mm,	Z =  1511.228  mm,
	W =  -178.202 deg,	P =    -7.992 deg,	R =   -92.416 deg
};
P[48]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2866.222  mm,	Y = -1077.718  mm,	Z =  1524.374  mm,
	W =  -176.819 deg,	P =     1.906 deg,	R =  -122.741 deg
};
P[49]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3749.543  mm,	Y =  -727.597  mm,	Z =  1508.165  mm,
	W =  -178.817 deg,	P =    -8.105 deg,	R =   -88.017 deg
};
P[50]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2832.095  mm,	Y = -1129.905  mm,	Z =  1530.930  mm,
	W =  -177.012 deg,	P =     2.197 deg,	R =  -128.132 deg
};
P[51]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2793.026  mm,	Y = -1179.126  mm,	Z =  1534.995  mm,
	W =  -177.245 deg,	P =     2.482 deg,	R =  -133.822 deg
};
P[52]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3661.208  mm,	Y =  -642.574  mm,	Z =  1718.140  mm,
	W =   142.308 deg,	P =    -5.320 deg,	R =   -89.000 deg
};
P[53]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3749.652  mm,	Y =  -749.300  mm,	Z =  1511.228  mm,
	W =  -178.202 deg,	P =    -7.992 deg,	R =   -92.416 deg
};
P[56]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3669.018  mm,	Y =  -828.777  mm,	Z =  1731.953  mm,
	W =   142.308 deg,	P =    -5.320 deg,	R =   -89.000 deg
};
P[57]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3661.208  mm,	Y =  -642.574  mm,	Z =  1718.140  mm,
	W =   142.308 deg,	P =    -5.320 deg,	R =   -89.000 deg
};
P[62]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3748.636  mm,	Y =  -711.451  mm,	Z =  1522.827  mm,
	W =  -178.817 deg,	P =    -8.104 deg,	R =   -88.017 deg
};
P[64]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.394  mm,	Y =  -751.142  mm,	Z =  1499.232  mm,
	W =  -176.293 deg,	P =      .079 deg,	R =   -93.059 deg
};
P[65]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2954.146  mm,	Y =  -793.202  mm,	Z =  1499.174  mm,
	W =  -176.303 deg,	P =      .290 deg,	R =   -96.319 deg
};
P[66]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2948.809  mm,	Y =  -839.711  mm,	Z =  1501.811  mm,
	W =  -176.337 deg,	P =      .578 deg,	R =  -100.798 deg
};
P[67]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2937.781  mm,	Y =  -895.569  mm,	Z =  1506.984  mm,
	W =  -176.395 deg,	P =      .867 deg,	R =  -105.343 deg
};
P[68]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2922.458  mm,	Y =  -949.707  mm,	Z =  1513.319  mm,
	W =  -176.486 deg,	P =     1.183 deg,	R =  -110.416 deg
};
P[69]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2898.984  mm,	Y = -1011.761  mm,	Z =  1517.701  mm,
	W =  -176.618 deg,	P =     1.520 deg,	R =  -116.017 deg
};
P[70]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2866.222  mm,	Y = -1077.718  mm,	Z =  1524.374  mm,
	W =  -176.819 deg,	P =     1.906 deg,	R =  -122.741 deg
};
P[71]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2832.095  mm,	Y = -1129.905  mm,	Z =  1530.930  mm,
	W =  -177.012 deg,	P =     2.197 deg,	R =  -128.132 deg
};
P[72]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2793.026  mm,	Y = -1179.126  mm,	Z =  1534.995  mm,
	W =  -177.245 deg,	P =     2.482 deg,	R =  -133.822 deg
};
P[73:"END"]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2769.980  mm,	Y = -1204.246  mm,	Z =  1536.899  mm,
	W =  -177.432 deg,	P =     2.674 deg,	R =  -137.989 deg
};
/END
