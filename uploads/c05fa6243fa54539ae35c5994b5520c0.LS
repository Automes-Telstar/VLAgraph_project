/PROG  S05PROC_N_TG
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "9QBC N TAILGATE";
PROG_SIZE	= 10894;
CREATE		= DATE 23-06-08  TIME 10:02:50;
MODIFIED	= DATE 25-08-04  TIME 06:48:26;
FILE_NAME	= S01PROC_;
VERSION		= 0;
LINE_COUNT	= 217;
MEMORY_SIZE	= 11354;
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
  DISPENSE : TRUE ; 
/MN
   1:  R[599:CSS RETRY]=0    ;
   2:  LBL[1] ;
   3:   ;
   4:  SET SEGMENT(51) ;
   5:  CALL CAPMES_R12    ;
   6:  UFRAME_NUM=2 ;
   7:  UTOOL_NUM=6 ;
   8:  CALL ISRACFG(2,4) ;
   9:  CALL STRTMEAS(60,2,0) ;
  10:   ;
  11:J P[1:POUNCE] 80% CNT100    ;
  12:   ;
  13:  ENTER I-ZONE(2) ;
  14:  ENTER I-ZONE(3) ;
  15:  ENTER I-ZONE(11) ;
  16:   ;
  17:J P[2:1] 80% FINE    ;
  18:  WAIT    .20(sec) ;
  19:  CALL ISRAPNT('M1',2,6) ;
  20:J P[3:2] 80% FINE    ;
  21:  WAIT    .20(sec) ;
  22:  CALL ISRAPNT('M2',2,6) ;
  23:J P[4:3] 80% FINE    ;
  24:  WAIT    .20(sec) ;
  25:  CALL ISRAPNT('M3',2,6) ;
  26:J P[5] 80% CNT100    ;
  27:J P[6:4] 80% FINE    ;
  28:  WAIT    .20(sec) ;
  29:  CALL ISRAPNT('M4',2,6) ;
  30:J P[7] 80% CNT100    ;
  31:J P[8:5] 80% FINE    ;
  32:  WAIT    .20(sec) ;
  33:  CALL ISRAPNT('M5',2,6) ;
  34:J P[9] 80% CNT50    ;
  35:  CALL ENDMEAS    ;
  36:  CALL STRTAPPL(2) ;
  37:  IF R[3:ISRAErrFlag]<>0,JMP LBL[100] ;
  38:   ;
  39:   ;
  40:  UFRAME_NUM=4 ;
  41:  UTOOL_NUM=7 ;
  42:  WAIT    .50(sec) ;
  43:  PR[26:ISRAApplPnts]=P[10]    ;
  44:  CALL ISRAPNT('A2') ;
  45:   ;
  46:J P[10] 80% CNT100    ;
  47:J P[11] 80% CNT100    ;
  48:J P[12] 80% CNT100    ;
  49:L P[13] 500mm/sec CNT30    ;
  50:L P[14] 500mm/sec CNT50    ;
  51:   ;
  52:  !1 ;
  53:L P[15] 500mm/sec CNT50    ;
  54:L P[16] 500mm/sec CNT50 SS[5]    ;
  55:L P[17] 500mm/sec CNT100    ;
  56:L P[18] 500mm/sec CNT100    ;
  57:L P[19] 500mm/sec CNT100    ;
  58:L P[20] 500mm/sec CNT100    ;
  59:L P[21] 500mm/sec CNT100    ;
  60:L P[22] 500mm/sec CNT100    ;
  61:L P[23] 500mm/sec CNT100    ;
  62:L P[24] 500mm/sec CNT100    ;
  63:L P[25] 500mm/sec CNT100    ;
  64:L P[26] 500mm/sec CNT100    ;
  65:L P[27] 500mm/sec CNT100    ;
  66:L P[28] 500mm/sec CNT100    ;
  67:L P[29] 500mm/sec CNT100    ;
  68:L P[30] 500mm/sec CNT100    ;
  69:L P[31] 500mm/sec CNT100    ;
  70:L P[32] 500mm/sec CNT100    ;
  71:L P[33] 500mm/sec CNT100    ;
  72:L P[34] 500mm/sec CNT100    ;
  73:L P[35] 500mm/sec CNT100    ;
  74:L P[36] 500mm/sec CNT100    ;
  75:L P[37] 500mm/sec CNT100    ;
  76:L P[38] 500mm/sec CNT100    ;
  77:L P[39] 500mm/sec CNT100    ;
  78:L P[40] 500mm/sec CNT100    ;
  79:L P[41] 500mm/sec CNT100    ;
  80:L P[42] 500mm/sec CNT100    ;
  81:L P[43] 500mm/sec CNT100    ;
  82:L P[44] 500mm/sec CNT100    ;
  83:L P[45] 500mm/sec CNT100    ;
  84:L P[46] 500mm/sec CNT100    ;
  85:L P[47] 500mm/sec CNT100    ;
  86:L P[48] 500mm/sec CNT100    ;
  87:L P[49] 500mm/sec CNT100    ;
  88:L P[50] 500mm/sec CNT100    ;
  89:L P[51] 500mm/sec CNT100    ;
  90:L P[52] 500mm/sec CNT100    ;
  91:L P[53] 500mm/sec CNT100    ;
  92:L P[54] 500mm/sec CNT100    ;
  93:L P[55] 500mm/sec CNT100    ;
  94:L P[56] 500mm/sec CNT100    ;
  95:L P[57] 500mm/sec CNT100    ;
  96:L P[58] 500mm/sec CNT50 SE    ;
  97:L P[59] 500mm/sec CNT50    ;
  98:L P[60] 500mm/sec CNT50    ;
  99:   ;
 100:  PR[26:ISRAApplPnts]=P[61]    ;
 101:  CALL ISRAPNT('A1') ;
 102:   ;
 103:  !2 ;
 104:L P[61] 500mm/sec CNT50    ;
 105:L P[62] 500mm/sec CNT50    ;
 106:L P[63] 500mm/sec CNT50 SS[5]    ;
 107:L P[64] 500mm/sec CNT100    ;
 108:L P[65] 500mm/sec CNT50 SE    ;
 109:L P[66] 500mm/sec CNT50    ;
 110:L P[67] 500mm/sec CNT100    ;
 111:   ;
 112:  !3 ;
 113:L P[68] 500mm/sec CNT100    ;
 114:L P[69] 500mm/sec CNT50    ;
 115:L P[70] 500mm/sec CNT50 SS[5]    ;
 116:L P[71] 500mm/sec CNT100    ;
 117:L P[72] 500mm/sec CNT100    ;
 118:L P[73] 500mm/sec CNT100    ;
 119:L P[74] 500mm/sec CNT100    ;
 120:L P[75] 500mm/sec CNT50 SE    ;
 121:L P[76] 500mm/sec CNT100    ;
 122:L P[77] 500mm/sec CNT100    ;
 123:L P[78] 500mm/sec CNT100    ;
 124:L P[79] 500mm/sec CNT100    ;
 125:L P[80] 500mm/sec CNT100    ;
 126:L P[81] 500mm/sec CNT100    ;
 127:L P[82] 500mm/sec CNT50    ;
 128:   ;
 129:   ;
 130:  !4 ;
 131:L P[83] 500mm/sec CNT50    ;
 132:L P[84] 500mm/sec CNT50    ;
 133:L P[85] 500mm/sec CNT50 SS[5]    ;
 134:L P[86] 500mm/sec CNT100    ;
 135:L P[87] 500mm/sec CNT100    ;
 136:L P[88] 500mm/sec CNT100    ;
 137:L P[89] 500mm/sec CNT50 SE    ;
 138:L P[90] 500mm/sec CNT50    ;
 139:L P[91] 500mm/sec CNT50    ;
 140:   ;
 141:L P[92] 500mm/sec CNT100    ;
 142:L P[93] 500mm/sec CNT100    ;
 143:L P[94] 500mm/sec CNT100    ;
 144:L P[95] 500mm/sec CNT30    ;
 145:L P[96] 500mm/sec CNT30    ;
 146:L P[97] 500mm/sec CNT30    ;
 147:L P[98] 500mm/sec CNT100    ;
 148:L P[99] 500mm/sec CNT100    ;
 149:L P[100] 500mm/sec CNT100    ;
 150:L P[101] 500mm/sec CNT100    ;
 151:L P[102] 500mm/sec CNT100    ;
 152:L P[103] 500mm/sec CNT100    ;
 153:L P[104] 500mm/sec CNT100    ;
 154:L P[105] 500mm/sec FINE    ;
 155:   ;
 156:  !5 ;
 157:L P[106] 500mm/sec CNT50    ;
 158:L P[107] 450mm/sec CNT50 SS[5]    ;
 159:L P[108] 450mm/sec CNT100    ;
 160:L P[109] 450mm/sec CNT100    ;
 161:L P[110] 500mm/sec CNT100    ;
 162:L P[111] 500mm/sec CNT100    ;
 163:L P[112] 500mm/sec CNT100    ;
 164:L P[113] 500mm/sec CNT100    ;
 165:L P[114] 500mm/sec CNT100    ;
 166:L P[115] 500mm/sec CNT100    ;
 167:L P[116] 500mm/sec CNT100    ;
 168:L P[117] 500mm/sec CNT100    ;
 169:L P[118] 500mm/sec CNT100    ;
 170:L P[119] 500mm/sec CNT100    ;
 171:L P[120] 500mm/sec CNT100    ;
 172:L P[121] 500mm/sec CNT100    ;
 173:L P[122] 500mm/sec CNT100    ;
 174:L P[123] 500mm/sec CNT100    ;
 175:L P[124] 500mm/sec CNT100    ;
 176:L P[125] 500mm/sec CNT100    ;
 177:L P[126] 500mm/sec CNT100    ;
 178:L P[127] 500mm/sec CNT100    ;
 179:L P[128] 500mm/sec CNT100    ;
 180:L P[129] 500mm/sec CNT100    ;
 181:L P[130] 500mm/sec CNT100    ;
 182:L P[131] 500mm/sec CNT100    ;
 183:L P[132] 500mm/sec CNT100    ;
 184:L P[133] 500mm/sec CNT50 SE    ;
 185:L P[134] 500mm/sec CNT50    ;
 186:L P[135] 500mm/sec CNT50    ;
 187:   ;
 188:L P[136] 500mm/sec CNT100    ;
 189:L P[137] 500mm/sec CNT100    ;
 190:J P[138] 40% CNT100    ;
 191:   ;
 192:J P[139:POUNCE] 40% CNT100    ;
 193:  CALL ENDAPPL    ;
 194:   ;
 195:  !@@ FREEPASS @@ ;
 196:  ENTER PLC ZONE(3) ;
 197:  EXIT I-ZONE(2) ;
 198:  EXIT I-ZONE(3) ;
 199:  EXIT I-ZONE(11) ;
 200:  JMP LBL[99] ;
 201:   ;
 202:  !CSS RETRY ;
 203:  LBL[100] ;
 204:  CALL ENDAPPL    ;
 205:  UFRAME_NUM=2 ;
 206:  UTOOL_NUM=6 ;
 207:J P[140] 30% CNT100    ;
 208:J P[141] 30% CNT100    ;
 209:J P[142:POUNCE] 40% CNT100    ;
 210:  R[599:CSS RETRY]=R[599:CSS RETRY]+1    ;
 211:  IF R[599:CSS RETRY]<2,JMP LBL[1] ;
 212:  DO[599:CSS RETRY ALARM]=ON ;
 213:  WAIT DI[5:Fault reset]=ON    ;
 214:  DO[599:CSS RETRY ALARM]=OFF ;
 215:  PAUSE ;
 216:   ;
 217:  LBL[99] ;
/POS
P[1:"POUNCE"]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   665.655  mm,	Y = -1471.002  mm,	Z =   362.772  mm,
	W =   -10.958 deg,	P =    89.377 deg,	R =    78.846 deg,
	E1=   500.000  mm
};
P[2:"1"]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =    83.422  mm,	Y =  -453.069  mm,	Z =   453.232  mm,
	W =  -133.875 deg,	P =    65.532 deg,	R =     4.560 deg,
	E1=  1091.395  mm
};
P[3:"2"]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   297.002  mm,	Y =  -449.483  mm,	Z =   362.260  mm,
	W =  -146.117 deg,	P =    47.073 deg,	R =    23.977 deg,
	E1=  1091.395  mm
};
P[4:"3"]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   473.595  mm,	Y =  -459.068  mm,	Z =   291.483  mm,
	W =  -149.323 deg,	P =    48.805 deg,	R =    15.715 deg,
	E1=  1091.395  mm
};
P[5:""]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   552.619  mm,	Y =  -492.612  mm,	Z =   281.146  mm,
	W =  -143.219 deg,	P =    52.275 deg,	R =    20.019 deg,
	E1=  1050.926  mm
};
P[6:"4"]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   528.625  mm,	Y =  -496.073  mm,	Z =    33.466  mm,
	W =  -110.767 deg,	P =    65.763 deg,	R =    41.954 deg,
	E1=   892.329  mm
};
P[7:""]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   830.824  mm,	Y =  -169.932  mm,	Z =    -9.535  mm,
	W =   -88.673 deg,	P =    11.493 deg,	R =    65.009 deg,
	E1=   507.097  mm
};
P[8:"5"]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   659.355  mm,	Y =   -98.377  mm,	Z =  -139.284  mm,
	W =   -89.552 deg,	P =     -.869 deg,	R =    85.606 deg,
	E1=   331.162  mm
};
P[9]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   846.719  mm,	Y =  -112.752  mm,	Z =  -140.753  mm,
	W =   -89.552 deg,	P =     -.869 deg,	R =    85.606 deg,
	E1=   331.162  mm
};
P[10]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =  1092.825  mm,	Y =     1.926  mm,	Z =  -208.977  mm,
	W =   -34.780 deg,	P =    89.073 deg,	R =    49.506 deg,
	E1=   331.162  mm
};
P[11]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =  1092.825  mm,	Y =     1.925  mm,	Z =  -208.977  mm,
	W =   179.183 deg,	P =      .605 deg,	R =    84.223 deg,
	E1=   331.162  mm
};
P[12]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   969.384  mm,	Y =   423.390  mm,	Z =  -224.230  mm,
	W =  -132.822 deg,	P =      .605 deg,	R =    84.223 deg,
	E1=   650.000  mm
};
P[13]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   640.533  mm,	Y =   361.628  mm,	Z =  -176.917  mm,
	W =  -106.081 deg,	P =      .605 deg,	R =    84.223 deg,
	E1=   650.000  mm
};
P[14]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   656.576  mm,	Y =   315.480  mm,	Z =  -135.023  mm,
	W =   -90.368 deg,	P =     -.188 deg,	R =    90.460 deg,
	E1=   650.000  mm
};
P[15]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   658.258  mm,	Y =   148.651  mm,	Z =  -132.740  mm,
	W =   -90.368 deg,	P =     -.188 deg,	R =    90.460 deg,
	E1=   650.000  mm
};
P[16]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   658.372  mm,	Y =   123.213  mm,	Z =  -133.633  mm,
	W =   -90.368 deg,	P =     -.188 deg,	R =    90.461 deg,
	E1=   650.000  mm
};
P[17]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   657.464  mm,	Y =   102.224  mm,	Z =  -133.685  mm,
	W =   -90.366 deg,	P =     -.046 deg,	R =    90.083 deg,
	E1=   650.000  mm
};
P[18]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   657.245  mm,	Y =    73.928  mm,	Z =  -134.846  mm,
	W =   -90.365 deg,	P =      .082 deg,	R =    89.739 deg,
	E1=   650.000  mm
};
P[19]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   657.137  mm,	Y =    48.762  mm,	Z =  -134.608  mm,
	W =   -90.364 deg,	P =      .197 deg,	R =    89.432 deg,
	E1=   650.000  mm
};
P[20]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   656.482  mm,	Y =    23.849  mm,	Z =  -134.391  mm,
	W =   -90.363 deg,	P =      .311 deg,	R =    89.129 deg,
	E1=   650.000  mm
};
P[21]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   655.797  mm,	Y =    -3.121  mm,	Z =  -134.364  mm,
	W =   -90.362 deg,	P =      .434 deg,	R =    88.800 deg,
	E1=   650.000  mm
};
P[22]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   655.076  mm,	Y =   -29.788  mm,	Z =  -133.937  mm,
	W =   -90.361 deg,	P =      .556 deg,	R =    88.475 deg,
	E1=   650.000  mm
};
P[23]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   652.998  mm,	Y =   -54.866  mm,	Z =  -133.920  mm,
	W =   -90.360 deg,	P =      .671 deg,	R =    88.169 deg,
	E1=   650.000  mm
};
P[24]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   652.208  mm,	Y =   -77.054  mm,	Z =  -133.899  mm,
	W =   -90.359 deg,	P =      .773 deg,	R =    87.899 deg,
	E1=   650.000  mm
};
P[25]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   650.420  mm,	Y =   -98.911  mm,	Z =  -133.673  mm,
	W =   -90.358 deg,	P =      .873 deg,	R =    87.632 deg,
	E1=   650.000  mm
};
P[26]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   648.779  mm,	Y =  -123.572  mm,	Z =  -133.632  mm,
	W =   -90.357 deg,	P =      .986 deg,	R =    87.331 deg,
	E1=   650.000  mm
};
P[27]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   646.967  mm,	Y =  -146.746  mm,	Z =  -133.594  mm,
	W =   -90.356 deg,	P =     1.093 deg,	R =    87.048 deg,
	E1=   650.000  mm
};
P[28]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   644.394  mm,	Y =  -173.200  mm,	Z =  -133.690  mm,
	W =   -90.355 deg,	P =     1.214 deg,	R =    86.725 deg,
	E1=   650.000  mm
};
P[29]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   641.709  mm,	Y =  -195.888  mm,	Z =  -133.610  mm,
	W =   -90.372 deg,	P =     1.402 deg,	R =    85.883 deg,
	E1=   650.000  mm
};
P[30]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   639.080  mm,	Y =  -221.597  mm,	Z =  -133.517  mm,
	W =   -90.393 deg,	P =     1.615 deg,	R =    84.930 deg,
	E1=   650.000  mm
};
P[31]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   635.350  mm,	Y =  -249.297  mm,	Z =  -133.422  mm,
	W =   -90.414 deg,	P =     1.845 deg,	R =    83.900 deg,
	E1=   650.000  mm
};
P[32]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   631.821  mm,	Y =  -274.704  mm,	Z =  -133.847  mm,
	W =   -90.434 deg,	P =     2.056 deg,	R =    82.956 deg,
	E1=   650.000  mm
};
P[33]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   628.349  mm,	Y =  -299.084  mm,	Z =  -133.887  mm,
	W =   -90.452 deg,	P =     2.258 deg,	R =    82.048 deg,
	E1=   650.000  mm
};
P[34]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   624.183  mm,	Y =  -325.270  mm,	Z =  -133.934  mm,
	W =   -90.473 deg,	P =     2.475 deg,	R =    81.071 deg,
	E1=   650.000  mm
};
P[35]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   619.111  mm,	Y =  -349.481  mm,	Z =  -133.989  mm,
	W =   -90.491 deg,	P =     2.677 deg,	R =    80.159 deg,
	E1=   650.000  mm
};
P[36]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   614.017  mm,	Y =  -373.531  mm,	Z =  -134.208  mm,
	W =   -90.510 deg,	P =     2.878 deg,	R =    79.253 deg,
	E1=   650.000  mm
};
P[37]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   607.726  mm,	Y =  -399.150  mm,	Z =  -134.944  mm,
	W =   -90.529 deg,	P =     3.093 deg,	R =    78.281 deg,
	E1=   650.000  mm
};
P[38]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   604.837  mm,	Y =  -409.617  mm,	Z =  -136.602  mm,
	W =   -91.751 deg,	P =     9.485 deg,	R =    76.521 deg,
	E1=   650.000  mm
};
P[39]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   601.656  mm,	Y =  -420.922  mm,	Z =  -136.312  mm,
	W =   -93.174 deg,	P =    16.427 deg,	R =    74.257 deg,
	E1=   650.000  mm
};
P[40]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   598.610  mm,	Y =  -430.729  mm,	Z =  -136.391  mm,
	W =   -94.529 deg,	P =    22.371 deg,	R =    71.988 deg,
	E1=   650.000  mm
};
P[41]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   595.240  mm,	Y =  -441.249  mm,	Z =  -135.988  mm,
	W =   -96.206 deg,	P =    28.775 deg,	R =    69.134 deg,
	E1=   650.000  mm
};
P[42]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   591.497  mm,	Y =  -452.483  mm,	Z =  -130.875  mm,
	W =   -98.897 deg,	P =    37.091 deg,	R =    64.628 deg,
	E1=   650.000  mm
};
P[43]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   588.134  mm,	Y =  -459.585  mm,	Z =  -124.326  mm,
	W =  -100.348 deg,	P =    41.023 deg,	R =    62.782 deg,
	E1=   650.000  mm
};
P[44]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   584.781  mm,	Y =  -465.627  mm,	Z =  -115.689  mm,
	W =  -102.150 deg,	P =    45.154 deg,	R =    60.504 deg,
	E1=   650.000  mm
};
P[45]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   582.344  mm,	Y =  -469.180  mm,	Z =  -105.079  mm,
	W =  -104.225 deg,	P =    49.095 deg,	R =    57.915 deg,
	E1=   650.000  mm
};
P[46]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   578.115  mm,	Y =  -473.867  mm,	Z =   -91.171  mm,
	W =  -107.921 deg,	P =    54.534 deg,	R =    53.404 deg,
	E1=   650.000  mm
};
P[47]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   569.831  mm,	Y =  -478.538  mm,	Z =   -75.929  mm,
	W =  -111.061 deg,	P =    58.482 deg,	R =    49.445 deg,
	E1=   650.000  mm
};
P[48]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   564.199  mm,	Y =  -479.267  mm,	Z =   -68.962  mm,
	W =  -112.790 deg,	P =    60.260 deg,	R =    47.326 deg,
	E1=   650.000  mm
};
P[49]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   558.750  mm,	Y =  -479.079  mm,	Z =   -62.462  mm,
	W =  -114.552 deg,	P =    61.848 deg,	R =    45.202 deg,
	E1=   650.000  mm
};
P[50]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   552.352  mm,	Y =  -480.372  mm,	Z =   -55.031  mm,
	W =  -116.990 deg,	P =    63.740 deg,	R =    42.313 deg,
	E1=   650.000  mm
};
P[51]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   546.192  mm,	Y =  -481.412  mm,	Z =   -47.189  mm,
	W =  -119.875 deg,	P =    65.615 deg,	R =    38.956 deg,
	E1=   650.000  mm
};
P[52]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   540.460  mm,	Y =  -483.467  mm,	Z =   -39.355  mm,
	W =  -123.258 deg,	P =    67.426 deg,	R =    35.087 deg,
	E1=   650.000  mm
};
P[53]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   533.651  mm,	Y =  -484.662  mm,	Z =   -24.914  mm,
	W =  -128.328 deg,	P =    69.696 deg,	R =    29.309 deg,
	E1=   650.000  mm
};
P[54]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   530.255  mm,	Y =  -485.833  mm,	Z =   -15.127  mm,
	W =  -128.097 deg,	P =    70.336 deg,	R =    28.467 deg,
	E1=   650.000  mm
};
P[55]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   527.804  mm,	Y =  -484.530  mm,	Z =    -2.724  mm,
	W =  -127.816 deg,	P =    71.097 deg,	R =    27.495 deg,
	E1=   650.000  mm
};
P[56]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   522.433  mm,	Y =  -486.494  mm,	Z =    22.235  mm,
	W =  -127.187 deg,	P =    72.728 deg,	R =    25.517 deg,
	E1=   650.000  mm
};
P[57]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   516.037  mm,	Y =  -487.606  mm,	Z =    51.329  mm,
	W =  -126.384 deg,	P =    74.688 deg,	R =    23.326 deg,
	E1=   650.000  mm
};
P[58]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   510.443  mm,	Y =  -488.425  mm,	Z =    78.291  mm,
	W =  -125.547 deg,	P =    76.560 deg,	R =    21.431 deg,
	E1=   650.000  mm
};
P[59]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   506.520  mm,	Y =  -489.413  mm,	Z =    93.800  mm,
	W =  -125.494 deg,	P =    76.672 deg,	R =    21.325 deg,
	E1=   650.000  mm
};
P[60]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   485.613  mm,	Y =  -496.371  mm,	Z =   157.647  mm,
	W =  -125.494 deg,	P =    76.672 deg,	R =    21.325 deg,
	E1=   650.000  mm
};
P[61]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   484.316  mm,	Y =  -535.350  mm,	Z =    16.727  mm,
	W =   101.771 deg,	P =    56.193 deg,	R =  -118.649 deg,
	E1=   650.000  mm
};
P[62]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   510.987  mm,	Y =  -499.798  mm,	Z =    74.076  mm,
	W =   101.771 deg,	P =    56.193 deg,	R =  -118.649 deg,
	E1=   650.000  mm
};
P[63]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   516.660  mm,	Y =  -489.949  mm,	Z =    84.611  mm,
	W =   101.771 deg,	P =    56.193 deg,	R =  -118.649 deg,
	E1=   650.000  mm
};
P[64]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   522.323  mm,	Y =  -480.060  mm,	Z =    95.467  mm,
	W =   101.772 deg,	P =    56.193 deg,	R =  -118.648 deg,
	E1=   650.000  mm
};
P[65]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   529.136  mm,	Y =  -466.731  mm,	Z =   117.190  mm,
	W =   101.771 deg,	P =    56.193 deg,	R =  -118.649 deg,
	E1=   650.000  mm
};
P[66]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   527.426  mm,	Y =  -462.630  mm,	Z =   125.871  mm,
	W =   101.773 deg,	P =    56.193 deg,	R =  -118.647 deg,
	E1=   650.000  mm
};
P[67]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   527.614  mm,	Y =  -458.148  mm,	Z =   133.996  mm,
	W =   100.359 deg,	P =    57.894 deg,	R =  -117.102 deg,
	E1=   650.000  mm
};
P[68]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   529.706  mm,	Y =  -453.896  mm,	Z =   140.206  mm,
	W =    99.037 deg,	P =    59.390 deg,	R =  -115.912 deg,
	E1=   650.000  mm
};
P[69]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   535.557  mm,	Y =  -450.939  mm,	Z =   149.818  mm,
	W =    97.772 deg,	P =    60.739 deg,	R =  -114.982 deg,
	E1=   650.000  mm
};
P[70]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   537.898  mm,	Y =  -446.554  mm,	Z =   158.589  mm,
	W =    96.507 deg,	P =    62.006 deg,	R =  -114.236 deg,
	E1=   650.000  mm
};
P[71]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   541.922  mm,	Y =  -435.997  mm,	Z =   178.462  mm,
	W =   110.011 deg,	P =    72.398 deg,	R =   -99.615 deg,
	E1=   650.000  mm
};
P[72]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   543.581  mm,	Y =  -429.341  mm,	Z =   191.914  mm,
	W =   145.949 deg,	P =    78.698 deg,	R =   -63.397 deg,
	E1=   650.000  mm
};
P[73]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   544.445  mm,	Y =  -424.898  mm,	Z =   202.878  mm,
	W =  -171.073 deg,	P =    77.717 deg,	R =   -19.745 deg,
	E1=   650.000  mm
};
P[74]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   544.573  mm,	Y =  -421.295  mm,	Z =   213.758  mm,
	W =  -145.842 deg,	P =    71.772 deg,	R =     6.607 deg,
	E1=   650.000  mm
};
P[75]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   542.418  mm,	Y =  -419.971  mm,	Z =   224.222  mm,
	W =  -134.033 deg,	P =    63.362 deg,	R =    20.169 deg,
	E1=   650.000  mm
};
P[76]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   539.156  mm,	Y =  -421.673  mm,	Z =   233.027  mm,
	W =  -128.164 deg,	P =    53.604 deg,	R =    28.614 deg,
	E1=   650.000  mm
};
P[77]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   534.383  mm,	Y =  -428.593  mm,	Z =   241.234  mm,
	W =  -125.939 deg,	P =    42.869 deg,	R =    34.592 deg,
	E1=   650.000  mm
};
P[78]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   527.656  mm,	Y =  -439.308  mm,	Z =   245.777  mm,
	W =  -125.554 deg,	P =    31.738 deg,	R =    40.140 deg,
	E1=   650.000  mm
};
P[79]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   521.162  mm,	Y =  -449.559  mm,	Z =   248.989  mm,
	W =  -126.437 deg,	P =    21.639 deg,	R =    45.416 deg,
	E1=   650.000  mm
};
P[80]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   513.729  mm,	Y =  -459.714  mm,	Z =   250.233  mm,
	W =  -128.323 deg,	P =    12.062 deg,	R =    51.158 deg,
	E1=   650.000  mm
};
P[81]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   507.896  mm,	Y =  -470.155  mm,	Z =   249.368  mm,
	W =  -128.323 deg,	P =    12.062 deg,	R =    51.158 deg,
	E1=   650.000  mm
};
P[82]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   469.025  mm,	Y =  -525.521  mm,	Z =   254.874  mm,
	W =  -128.323 deg,	P =    12.062 deg,	R =    51.158 deg,
	E1=   650.000  mm
};
P[83]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   538.222  mm,	Y =  -480.341  mm,	Z =   211.866  mm,
	W =  -175.519 deg,	P =    45.256 deg,	R =   -21.373 deg,
	E1=   650.000  mm
};
P[84]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   519.377  mm,	Y =  -468.703  mm,	Z =   240.448  mm,
	W =  -175.519 deg,	P =    45.256 deg,	R =   -21.373 deg,
	E1=   650.000  mm
};
P[85]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   507.122  mm,	Y =  -463.710  mm,	Z =   252.372  mm,
	W =  -175.530 deg,	P =    45.114 deg,	R =   -21.389 deg,
	E1=   650.000  mm
};
P[86]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   497.256  mm,	Y =  -458.955  mm,	Z =   263.307  mm,
	W =  -175.616 deg,	P =    43.985 deg,	R =   -21.511 deg,
	E1=   650.000  mm
};
P[87]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   482.247  mm,	Y =  -453.505  mm,	Z =   275.611  mm,
	W =  -175.721 deg,	P =    42.521 deg,	R =   -21.664 deg,
	E1=   650.000  mm
};
P[88]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   458.648  mm,	Y =  -445.696  mm,	Z =   292.191  mm,
	W =  -175.860 deg,	P =    40.368 deg,	R =   -21.875 deg,
	E1=   650.000  mm
};
P[89]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   438.103  mm,	Y =  -439.136  mm,	Z =   304.353  mm,
	W =  -175.964 deg,	P =    38.600 deg,	R =   -22.039 deg,
	E1=   650.000  mm
};
P[90]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   427.344  mm,	Y =  -436.046  mm,	Z =   308.292  mm,
	W =  -175.965 deg,	P =    38.599 deg,	R =   -22.039 deg,
	E1=   650.000  mm
};
P[91]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   411.508  mm,	Y =  -431.208  mm,	Z =   304.213  mm,
	W =  -175.964 deg,	P =    38.599 deg,	R =   -22.039 deg,
	E1=   650.000  mm
};
P[92]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   391.960  mm,	Y =  -459.739  mm,	Z =   308.712  mm,
	W =  -175.965 deg,	P =    38.600 deg,	R =   -22.039 deg,
	E1=   650.000  mm
};
P[93]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   369.944  mm,	Y =  -489.802  mm,	Z =   315.696  mm,
	W =  -175.965 deg,	P =    38.600 deg,	R =   -22.039 deg,
	E1=   650.000  mm
};
P[94]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   282.523  mm,	Y =  -525.210  mm,	Z =   374.641  mm,
	W =  -155.680 deg,	P =    28.860 deg,	R =     3.364 deg,
	E1=   753.164  mm
};
P[95]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =    16.505  mm,	Y =  -481.367  mm,	Z =   527.995  mm,
	W =  -148.348 deg,	P =   -23.204 deg,	R =    49.154 deg,
	E1=  1050.000  mm
};
P[96]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =     4.918  mm,	Y =  -446.338  mm,	Z =   480.203  mm,
	W =  -148.348 deg,	P =   -23.204 deg,	R =    49.153 deg,
	E1=  1050.000  mm
};
P[97]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =    -3.429  mm,	Y =  -437.716  mm,	Z =   493.585  mm,
	W =  -142.285 deg,	P =    16.334 deg,	R =     4.479 deg,
	E1=  1050.000  mm
};
P[98]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   -13.692  mm,	Y =  -431.021  mm,	Z =   504.241  mm,
	W =  -145.895 deg,	P =    32.567 deg,	R =    -8.082 deg,
	E1=  1049.978  mm
};
P[99]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -24.185  mm,	Y =  -419.721  mm,	Z =   514.884  mm,
	W =  -162.871 deg,	P =    34.626 deg,	R =   -36.396 deg,
	E1=  1049.978  mm
};
P[100]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -37.804  mm,	Y =  -405.143  mm,	Z =   526.170  mm,
	W =  -167.923 deg,	P =    29.805 deg,	R =   -46.652 deg,
	E1=  1049.978  mm
};
P[101]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -47.606  mm,	Y =  -389.437  mm,	Z =   536.566  mm,
	W =  -173.821 deg,	P =    24.101 deg,	R =   -58.460 deg,
	E1=  1049.978  mm
};
P[102]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -54.889  mm,	Y =  -368.260  mm,	Z =   544.558  mm,
	W =  -178.913 deg,	P =    18.766 deg,	R =   -70.843 deg,
	E1=  1049.978  mm
};
P[103]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -56.357  mm,	Y =  -352.373  mm,	Z =   549.455  mm,
	W =   179.882 deg,	P =    12.761 deg,	R =   -76.275 deg,
	E1=  1049.978  mm
};
P[104]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -57.138  mm,	Y =  -336.298  mm,	Z =   553.504  mm,
	W =   179.168 deg,	P =     8.021 deg,	R =   -81.381 deg,
	E1=  1049.978  mm
};
P[105]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -59.523  mm,	Y =  -316.693  mm,	Z =   557.364  mm,
	W =   179.383 deg,	P =    12.746 deg,	R =   -78.535 deg,
	E1=  1049.978  mm
};
P[106]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -55.626  mm,	Y =  -334.747  mm,	Z =   551.989  mm,
	W =   179.383 deg,	P =    12.747 deg,	R =   -78.535 deg,
	E1=  1049.978  mm
};
P[107]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -53.061  mm,	Y =  -349.481  mm,	Z =   549.545  mm,
	W =   179.383 deg,	P =    12.747 deg,	R =   -78.535 deg,
	E1=  1049.978  mm
};
P[108]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -53.783  mm,	Y =  -361.083  mm,	Z =   546.635  mm,
	W =   178.795 deg,	P =    15.547 deg,	R =   -74.326 deg,
	E1=  1049.978  mm
};
P[109]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -49.588  mm,	Y =  -369.070  mm,	Z =   543.136  mm,
	W =   178.607 deg,	P =    17.975 deg,	R =   -70.853 deg,
	E1=  1049.978  mm
};
P[110]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -48.292  mm,	Y =  -377.066  mm,	Z =   540.672  mm,
	W =   178.677 deg,	P =    20.161 deg,	R =   -67.797 deg,
	E1=  1049.978  mm
};
P[111]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -47.709  mm,	Y =  -386.880  mm,	Z =   536.379  mm,
	W =   179.070 deg,	P =    22.837 deg,	R =   -64.075 deg,
	E1=  1049.978  mm
};
P[112]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -42.541  mm,	Y =  -395.876  mm,	Z =   531.467  mm,
	W =   179.927 deg,	P =    25.881 deg,	R =   -59.806 deg,
	E1=  1049.978  mm
};
P[113]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -39.843  mm,	Y =  -402.094  mm,	Z =   527.275  mm,
	W =  -178.700 deg,	P =    27.019 deg,	R =   -55.077 deg,
	E1=  1049.978  mm
};
P[114]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -35.511  mm,	Y =  -408.051  mm,	Z =   522.667  mm,
	W =  -176.983 deg,	P =    28.192 deg,	R =   -49.868 deg,
	E1=  1049.978  mm
};
P[115]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, -1',
	X =   -29.424  mm,	Y =  -413.836  mm,	Z =   517.648  mm,
	W =  -174.753 deg,	P =    29.396 deg,	R =   -43.882 deg,
	E1=  1049.978  mm
};
P[116]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   -23.250  mm,	Y =  -419.721  mm,	Z =   512.174  mm,
	W =  -172.100 deg,	P =    30.480 deg,	R =   -37.505 deg,
	E1=  1049.978  mm
};
P[117]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   -15.324  mm,	Y =  -424.891  mm,	Z =   505.698  mm,
	W =  -168.696 deg,	P =    31.440 deg,	R =   -30.097 deg,
	E1=  1049.978  mm
};
P[118]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =    -8.383  mm,	Y =  -429.360  mm,	Z =   501.718  mm,
	W =  -165.659 deg,	P =    31.952 deg,	R =   -23.988 deg,
	E1=  1049.978  mm
};
P[119]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =     -.655  mm,	Y =  -433.223  mm,	Z =   495.660  mm,
	W =  -163.361 deg,	P =    31.869 deg,	R =   -21.159 deg,
	E1=  1049.978  mm
};
P[120]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =     7.892  mm,	Y =  -435.994  mm,	Z =   489.055  mm,
	W =  -160.925 deg,	P =    31.640 deg,	R =   -18.189 deg,
	E1=  1049.978  mm
};
P[121]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =    18.554  mm,	Y =  -438.495  mm,	Z =   482.425  mm,
	W =  -158.135 deg,	P =    31.199 deg,	R =   -14.819 deg,
	E1=  1049.978  mm
};
P[122]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =    31.707  mm,	Y =  -441.962  mm,	Z =   474.049  mm,
	W =  -154.705 deg,	P =    30.386 deg,	R =   -10.713 deg,
	E1=  1049.978  mm
};
P[123]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =    48.782  mm,	Y =  -441.613  mm,	Z =   464.177  mm,
	W =  -150.603 deg,	P =    28.996 deg,	R =    -5.849 deg,
	E1=  1049.978  mm
};
P[124]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =    78.718  mm,	Y =  -440.204  mm,	Z =   449.972  mm,
	W =  -144.060 deg,	P =    25.694 deg,	R =     1.825 deg,
	E1=  1049.978  mm
};
P[125]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   108.603  mm,	Y =  -439.173  mm,	Z =   434.963  mm,
	W =  -144.936 deg,	P =    25.331 deg,	R =     2.224 deg,
	E1=  1049.978  mm
};
P[126]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   144.379  mm,	Y =  -438.976  mm,	Z =   418.426  mm,
	W =  -145.966 deg,	P =    24.920 deg,	R =     2.708 deg,
	E1=  1049.978  mm
};
P[127]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.122  mm,	Y =  -439.239  mm,	Z =   402.717  mm,
	W =  -146.983 deg,	P =    24.532 deg,	R =     3.201 deg,
	E1=  1049.978  mm
};
P[128]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   215.470  mm,	Y =  -439.360  mm,	Z =   387.920  mm,
	W =  -147.980 deg,	P =    24.168 deg,	R =     3.698 deg,
	E1=  1049.978  mm
};
P[129]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   256.517  mm,	Y =  -439.024  mm,	Z =   370.574  mm,
	W =  -149.137 deg,	P =    23.768 deg,	R =     4.293 deg,
	E1=  1049.978  mm
};
P[130]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   297.565  mm,	Y =  -437.812  mm,	Z =   353.123  mm,
	W =  -150.295 deg,	P =    23.393 deg,	R =     4.905 deg,
	E1=  1049.978  mm
};
P[131]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   330.869  mm,	Y =  -436.395  mm,	Z =   339.001  mm,
	W =  -151.234 deg,	P =    23.107 deg,	R =     5.413 deg,
	E1=  1049.978  mm
};
P[132]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   355.859  mm,	Y =  -433.505  mm,	Z =   328.355  mm,
	W =  -151.944 deg,	P =    22.902 deg,	R =     5.804 deg,
	E1=  1049.978  mm
};
P[133]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   385.219  mm,	Y =  -428.819  mm,	Z =   316.540  mm,
	W =  -152.773 deg,	P =    22.675 deg,	R =     6.267 deg,
	E1=  1049.978  mm
};
P[134]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   396.621  mm,	Y =  -428.131  mm,	Z =   311.475  mm,
	W =  -152.773 deg,	P =    22.675 deg,	R =     6.267 deg,
	E1=  1049.978  mm
};
P[135]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   410.909  mm,	Y =  -428.733  mm,	Z =   303.290  mm,
	W =  -152.773 deg,	P =    22.675 deg,	R =     6.267 deg,
	E1=  1049.978  mm
};
P[136]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   446.909  mm,	Y =  -464.016  mm,	Z =   279.369  mm,
	W =  -168.998 deg,	P =    33.293 deg,	R =   -15.575 deg,
	E1=  1050.000  mm
};
P[137]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   450.272  mm,	Y =  -519.349  mm,	Z =   264.951  mm,
	W =  -168.998 deg,	P =    33.293 deg,	R =   -15.575 deg,
	E1=  1050.000  mm
};
P[138]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   433.764  mm,	Y =  -620.544  mm,	Z =   282.109  mm,
	W =  -168.998 deg,	P =    33.293 deg,	R =   -15.575 deg,
	E1=  1050.000  mm
};
P[139:"POUNCE"]{
   GP1:
	UF : 4, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =   574.594  mm,	Y = -1722.926  mm,	Z =   226.179  mm,
	W =  -179.774 deg,	P =      .107 deg,	R =   179.993 deg,
	E1=   500.000  mm
};
P[140]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   844.396  mm,	Y =  -112.555  mm,	Z =  -140.717  mm,
	W =   -89.552 deg,	P =     -.869 deg,	R =    85.606 deg,
	E1=   331.162  mm
};
P[141]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   798.667  mm,	Y =  -488.212  mm,	Z =   183.718  mm,
	W =   -48.666 deg,	P =    12.731 deg,	R =    75.595 deg,
	E1=   382.242  mm
};
P[142:"POUNCE"]{
   GP1:
	UF : 2, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =   647.843  mm,	Y = -1487.183  mm,	Z =   364.848  mm,
	W =   -10.520 deg,	P =    88.871 deg,	R =    78.459 deg,
	E1=   500.000  mm
};
/END
