/PROG  S05PROC
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "9QBC F50mm R90mm";
PROG_SIZE	= 5785;
CREATE		= DATE 21-09-06  TIME 09:10:42;
MODIFIED	= DATE 21-09-06  TIME 11:06:38;
FILE_NAME	= S01PROC;
VERSION		= 0;
LINE_COUNT	= 130;
MEMORY_SIZE	= 6149;
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
  10:J P[1:POUNCE] 30% CNT100    ;
  11:   ;
  12:  !Front Door 1st Open ;
  13:J P[78] 30% CNT100    ;
  14:L P[77] 500mm/sec CNT50    ;
  15:L P[76] 500mm/sec CNT100    ;
  16:L P[75] 150mm/sec FINE    ;
  17:L P[74] 150mm/sec FINE    ;
  18:  WAIT    .30(sec) ;
  19:L P[5] 150mm/sec FINE    ;
  20:L P[8:END] 250mm/sec FINE    ;
  21:   ;
  22:  EXIT I-ZONE(6) ;
  23:   ;
  24:  !@@ WAIT R4 DO[602]-ON @@ ;
  25:  ENTER PLC ZONE(1) ;
  26:   ;
  27:  ENTER I-ZONE(5) ;
  28:  ENTER I-ZONE(6) ;
  29:   ;
  30:  !Front Door 2nd Open ;
  31:L P[9] 300mm/sec FINE    ;
  32:L P[10] 300mm/sec CNT100    ;
  33:L P[11] 300mm/sec CNT100    ;
  34:L P[12] 300mm/sec CNT100    ;
  35:L P[13] 300mm/sec CNT100    ;
  36:L P[14] 300mm/sec CNT100    ;
  37:L P[7] 300mm/sec CNT100    ;
  38:L P[46] 300mm/sec CNT100    ;
  39:L P[47] 300mm/sec CNT100    ;
  40:L P[48] 300mm/sec CNT100    ;
  41:L P[49] 300mm/sec CNT100    ;
  42:L P[50] 300mm/sec CNT100    ;
  43:L P[59] 300mm/sec CNT100    ;
  44:L P[35] 300mm/sec FINE    ;
  45:   ;
  46:  !@@ WAIT Stopper On @@ ;
  47:  ENTER PLC ZONE(2) ;
  48:  WAIT   1.00(sec) ;
  49:   ;
  50:  !Front Door -) Rear Door ;
  51:L P[16:END] 250mm/sec FINE    ;
  52:L P[31] 500mm/sec CNT50    ;
  53:J P[18] 80% CNT100    ;
  54:J P[53] 80% CNT100    ;
  55:J P[19] 80% CNT100    ;
  56:J P[20] 80% CNT100    ;
  57:J P[21] 80% CNT100    ;
  58:J P[22] 80% CNT50    ;
  59:J P[64] 80% CNT50    ;
  60:   ;
  61:  !Rear Door Open ;
  62:L P[36] 500mm/sec CNT50    ;
  63:L P[17] 500mm/sec CNT100    ;
  64:L P[23] 250mm/sec FINE    ;
  65:L P[60] 150mm/sec FINE    ;
  66:  WAIT    .30(sec) ;
  67:L P[24] 150mm/sec CNT100    ;
  68:L P[26] 150mm/sec FINE    ;
  69:   ;
  70:  EXIT I-ZONE(5) ;
  71:   ;
  72:  !@@ WAIT R2 DO[603]-ON @@ ;
  73:  ENTER PLC ZONE(3) ;
  74:  SET SEGMENT(30) ;
  75:   ;
  76:  ENTER I-ZONE(5) ;
  77:  ENTER I-ZONE(6) ;
  78:   ;
  79:  !Rear Door Close ;
  80:L P[70] 150mm/sec FINE    ;
  81:L P[69] 150mm/sec CNT100    ;
  82:L P[63] 150mm/sec FINE    ;
  83:  WAIT    .30(sec) ;
  84:L P[62] 250mm/sec FINE    ;
  85:L P[61] 500mm/sec CNT100    ;
  86:L P[25] 500mm/sec CNT50    ;
  87:   ;
  88:  !Rear Door -) Front Door ;
  89:J P[43] 80% CNT50    ;
  90:J P[42] 80% CNT50    ;
  91:J P[41] 80% CNT100    ;
  92:J P[40] 80% CNT100    ;
  93:J P[39] 80% CNT100    ;
  94:J P[30] 80% CNT100    ;
  95:J P[29] 80% CNT100    ;
  96:L P[28] 500mm/sec CNT50    ;
  97:L P[27:END] 250mm/sec FINE    ;
  98:   ;
  99:  !@@ WAIT Stopper Off @@ ;
 100:  WAIT   1.00(sec) ;
 101:  ENTER PLC ZONE(4) ;
 102:  WAIT   1.00(sec) ;
 103:   ;
 104:  !Front Door Close ;
 105:L P[65] 300mm/sec FINE    ;
 106:L P[58] 300mm/sec CNT100    ;
 107:L P[57] 300mm/sec CNT100    ;
 108:L P[56] 300mm/sec CNT100    ;
 109:L P[55] 300mm/sec CNT100    ;
 110:L P[54] 300mm/sec CNT100    ;
 111:L P[52] 300mm/sec CNT100    ;
 112:L P[45] 300mm/sec CNT100    ;
 113:L P[44] 300mm/sec CNT100    ;
 114:L P[38] 300mm/sec CNT100    ;
 115:L P[37] 300mm/sec CNT100    ;
 116:L P[34] 300mm/sec CNT100    ;
 117:L P[33] 300mm/sec CNT100    ;
 118:L P[32] 300mm/sec CNT100    ;
 119:L P[73] 150mm/sec FINE    ;
 120:  WAIT    .30(sec) ;
 121:L P[72] 150mm/sec FINE    ;
 122:L P[71] 150mm/sec FINE    ;
 123:L P[68] 500mm/sec CNT100    ;
 124:L P[67] 500mm/sec CNT50    ;
 125:J P[66] 30% CNT100    ;
 126:   ;
 127:J P[51:POUNCE] 30% CNT100    ;
 128:   ;
 129:  EXIT I-ZONE(5) ;
 130:  EXIT I-ZONE(6) ;
/POS
P[1:"POUNCE"]{
   GP1:
	UF : 1, UT : 1,	
	J1=    15.355 deg,	J2=    -9.066 deg,	J3=   -22.674 deg,
	J4=   140.038 deg,	J5=   -26.974 deg,	J6=  -142.352 deg
};
P[5]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.858  mm,	Y =   734.741  mm,	Z =  1483.870  mm,
	W =   178.606 deg,	P =     1.360 deg,	R =    91.595 deg
};
P[7]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2901.351  mm,	Y =  1013.796  mm,	Z =  1499.846  mm,
	W =   179.287 deg,	P =     1.820 deg,	R =   115.737 deg
};
P[8:"END"]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.173  mm,	Y =   762.974  mm,	Z =  1483.195  mm,
	W =   178.634 deg,	P =     1.394 deg,	R =    92.790 deg
};
P[9]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.168  mm,	Y =   762.922  mm,	Z =  1483.182  mm,
	W =   178.634 deg,	P =     1.396 deg,	R =    92.790 deg
};
P[10]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2954.369  mm,	Y =   797.625  mm,	Z =  1486.836  mm,
	W =   178.714 deg,	P =     1.470 deg,	R =    95.966 deg
};
P[11]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2951.157  mm,	Y =   827.675  mm,	Z =  1489.211  mm,
	W =   178.786 deg,	P =     1.530 deg,	R =    98.730 deg
};
P[12]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2945.000  mm,	Y =   867.245  mm,	Z =  1491.923  mm,
	W =   178.883 deg,	P =     1.602 deg,	R =   102.295 deg
};
P[13]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2935.413  mm,	Y =   910.643  mm,	Z =  1497.161  mm,
	W =   178.989 deg,	P =     1.671 deg,	R =   106.008 deg
};
P[14]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2918.146  mm,	Y =   970.447  mm,	Z =  1501.286  mm,
	W =   179.144 deg,	P =     1.755 deg,	R =   111.158 deg
};
P[16:"END"]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2712.553  mm,	Y =  1259.660  mm,	Z =  1519.677  mm,
	W =  -179.745 deg,	P =     1.935 deg,	R =   144.644 deg
};
P[17]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3759.529  mm,	Y =   700.069  mm,	Z =  1568.723  mm,
	W =   178.503 deg,	P =    -2.890 deg,	R =    87.454 deg
};
P[18]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2548.798  mm,	Y =  1376.738  mm,	Z =  1676.410  mm,
	W =  -179.745 deg,	P =     1.935 deg,	R =   144.644 deg
};
P[19]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2927.882  mm,	Y =  1882.362  mm,	Z =  1650.088  mm,
	W =  -178.144 deg,	P =    -7.661 deg,	R =    84.132 deg
};
P[20]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3269.720  mm,	Y =  1890.413  mm,	Z =  1643.943  mm,
	W =  -178.144 deg,	P =    -7.660 deg,	R =    84.132 deg
};
P[21]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3489.845  mm,	Y =  1087.501  mm,	Z =  1727.813  mm,
	W =  -131.447 deg,	P =    -4.900 deg,	R =   101.084 deg
};
P[22]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3551.097  mm,	Y =   709.566  mm,	Z =  1722.916  mm,
	W =  -131.447 deg,	P =    -4.901 deg,	R =   101.083 deg
};
P[23]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3761.055  mm,	Y =   718.612  mm,	Z =  1512.437  mm,
	W =   178.470 deg,	P =    -2.873 deg,	R =    88.115 deg
};
P[24]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3761.396  mm,	Y =   728.944  mm,	Z =  1512.956  mm,
	W =   178.470 deg,	P =    -2.874 deg,	R =    88.115 deg
};
P[25]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3756.829  mm,	Y =   650.389  mm,	Z =  1621.103  mm,
	W =   178.360 deg,	P =    -2.811 deg,	R =    90.344 deg
};
P[26:""]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3762.196  mm,	Y =   753.201  mm,	Z =  1514.175  mm,
	W =   178.275 deg,	P =    -2.761 deg,	R =    92.078 deg
};
P[27:"END"]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2712.553  mm,	Y =  1259.660  mm,	Z =  1519.677  mm,
	W =  -179.745 deg,	P =     1.935 deg,	R =   144.644 deg
};
P[28:""]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2722.971  mm,	Y =  1253.070  mm,	Z =  1667.057  mm,
	W =  -179.745 deg,	P =     1.935 deg,	R =   144.644 deg
};
P[29]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2548.798  mm,	Y =  1376.738  mm,	Z =  1676.410  mm,
	W =  -179.745 deg,	P =     1.935 deg,	R =   144.644 deg
};
P[30]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2570.322  mm,	Y =  1704.045  mm,	Z =  1583.798  mm,
	W =   179.438 deg,	P =    -7.158 deg,	R =   102.738 deg
};
P[31:""]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2722.971  mm,	Y =  1253.070  mm,	Z =  1667.057  mm,
	W =  -179.745 deg,	P =     1.935 deg,	R =   144.644 deg
};
P[32]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.168  mm,	Y =   762.922  mm,	Z =  1483.182  mm,
	W =   178.634 deg,	P =     1.396 deg,	R =    92.790 deg
};
P[33]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2954.369  mm,	Y =   797.625  mm,	Z =  1486.836  mm,
	W =   178.714 deg,	P =     1.470 deg,	R =    95.966 deg
};
P[34]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2951.157  mm,	Y =   827.675  mm,	Z =  1489.211  mm,
	W =   178.786 deg,	P =     1.530 deg,	R =    98.730 deg
};
P[35]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2712.553  mm,	Y =  1259.660  mm,	Z =  1519.677  mm,
	W =  -179.745 deg,	P =     1.935 deg,	R =   144.644 deg
};
P[36]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3756.829  mm,	Y =   650.389  mm,	Z =  1621.103  mm,
	W =   178.360 deg,	P =    -2.811 deg,	R =    90.344 deg
};
P[37]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2945.000  mm,	Y =   867.245  mm,	Z =  1491.923  mm,
	W =   178.883 deg,	P =     1.602 deg,	R =   102.295 deg
};
P[38]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2935.413  mm,	Y =   910.643  mm,	Z =  1497.161  mm,
	W =   178.989 deg,	P =     1.671 deg,	R =   106.008 deg
};
P[39]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2927.882  mm,	Y =  1882.362  mm,	Z =  1650.088  mm,
	W =  -178.144 deg,	P =    -7.661 deg,	R =    84.132 deg
};
P[40]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3269.720  mm,	Y =  1890.413  mm,	Z =  1643.943  mm,
	W =  -178.144 deg,	P =    -7.660 deg,	R =    84.132 deg
};
P[41]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3489.845  mm,	Y =  1087.501  mm,	Z =  1727.813  mm,
	W =  -131.447 deg,	P =    -4.900 deg,	R =   101.084 deg
};
P[42]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3551.097  mm,	Y =   709.566  mm,	Z =  1722.916  mm,
	W =  -131.447 deg,	P =    -4.901 deg,	R =   101.083 deg
};
P[43]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3567.826  mm,	Y =   624.167  mm,	Z =  1715.455  mm,
	W =  -131.447 deg,	P =    -4.901 deg,	R =   101.083 deg
};
P[44]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2918.146  mm,	Y =   970.447  mm,	Z =  1501.286  mm,
	W =   179.144 deg,	P =     1.755 deg,	R =   111.158 deg
};
P[45]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2901.351  mm,	Y =  1013.796  mm,	Z =  1499.846  mm,
	W =   179.287 deg,	P =     1.820 deg,	R =   115.737 deg
};
P[46]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2884.515  mm,	Y =  1048.611  mm,	Z =  1502.400  mm,
	W =   179.403 deg,	P =     1.861 deg,	R =   119.352 deg
};
P[47]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2856.256  mm,	Y =  1098.677  mm,	Z =  1509.176  mm,
	W =   179.581 deg,	P =     1.909 deg,	R =   124.750 deg
};
P[48]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2822.014  mm,	Y =  1147.987  mm,	Z =  1510.957  mm,
	W =   179.747 deg,	P =     1.938 deg,	R =   129.703 deg
};
P[49]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2788.478  mm,	Y =  1188.351  mm,	Z =  1512.963  mm,
	W =   179.900 deg,	P =     1.951 deg,	R =   134.210 deg
};
P[50]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2760.482  mm,	Y =  1217.115  mm,	Z =  1517.539  mm,
	W =  -179.970 deg,	P =     1.953 deg,	R =   138.024 deg
};
P[51:"POUNCE"]{
   GP1:
	UF : 1, UT : 1,	
	J1=    15.355 deg,	J2=    -9.066 deg,	J3=   -22.674 deg,
	J4=   140.038 deg,	J5=   -26.974 deg,	J6=  -142.352 deg
};
P[52]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2884.515  mm,	Y =  1048.611  mm,	Z =  1502.400  mm,
	W =   179.403 deg,	P =     1.861 deg,	R =   119.352 deg
};
P[53]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2570.322  mm,	Y =  1704.045  mm,	Z =  1583.798  mm,
	W =   179.438 deg,	P =    -7.158 deg,	R =   102.738 deg
};
P[54]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2856.256  mm,	Y =  1098.677  mm,	Z =  1509.176  mm,
	W =   179.581 deg,	P =     1.909 deg,	R =   124.750 deg
};
P[55]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2822.014  mm,	Y =  1147.987  mm,	Z =  1510.957  mm,
	W =   179.747 deg,	P =     1.938 deg,	R =   129.703 deg
};
P[56]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2788.478  mm,	Y =  1188.351  mm,	Z =  1512.963  mm,
	W =   179.900 deg,	P =     1.951 deg,	R =   134.210 deg
};
P[57]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2760.482  mm,	Y =  1217.115  mm,	Z =  1517.539  mm,
	W =  -179.970 deg,	P =     1.953 deg,	R =   138.024 deg
};
P[58]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2716.241  mm,	Y =  1256.920  mm,	Z =  1519.833  mm,
	W =  -179.770 deg,	P =     1.939 deg,	R =   143.917 deg
};
P[59]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2716.241  mm,	Y =  1256.920  mm,	Z =  1519.833  mm,
	W =  -179.770 deg,	P =     1.939 deg,	R =   143.917 deg
};
P[60]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3761.293  mm,	Y =   725.800  mm,	Z =  1512.798  mm,
	W =   178.470 deg,	P =    -2.873 deg,	R =    88.115 deg
};
P[61]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3759.529  mm,	Y =   700.069  mm,	Z =  1568.723  mm,
	W =   178.503 deg,	P =    -2.890 deg,	R =    87.454 deg
};
P[62]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3761.055  mm,	Y =   718.612  mm,	Z =  1512.437  mm,
	W =   178.470 deg,	P =    -2.873 deg,	R =    88.115 deg
};
P[63]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3761.293  mm,	Y =   725.800  mm,	Z =  1512.798  mm,
	W =   178.470 deg,	P =    -2.873 deg,	R =    88.115 deg
};
P[64]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3567.826  mm,	Y =   624.167  mm,	Z =  1715.455  mm,
	W =  -131.447 deg,	P =    -4.901 deg,	R =   101.083 deg
};
P[65]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2712.553  mm,	Y =  1259.660  mm,	Z =  1519.677  mm,
	W =  -179.745 deg,	P =     1.935 deg,	R =   144.644 deg
};
P[66]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2952.272  mm,	Y =   693.817  mm,	Z =  1682.095  mm,
	W =   178.600 deg,	P =     1.354 deg,	R =    91.337 deg
};
P[67]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2951.545  mm,	Y =   687.386  mm,	Z =  1613.012  mm,
	W =   178.615 deg,	P =     1.332 deg,	R =    91.317 deg
};
P[68]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.848  mm,	Y =   716.329  mm,	Z =  1502.305  mm,
	W =   178.600 deg,	P =     1.353 deg,	R =    91.337 deg
};
P[69]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3761.396  mm,	Y =   728.944  mm,	Z =  1512.956  mm,
	W =   178.470 deg,	P =    -2.874 deg,	R =    88.115 deg
};
P[70:""]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  3762.196  mm,	Y =   753.201  mm,	Z =  1514.175  mm,
	W =   178.275 deg,	P =    -2.761 deg,	R =    92.078 deg
};
P[71]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.879  mm,	Y =   721.228  mm,	Z =  1496.190  mm,
	W =   178.600 deg,	P =     1.353 deg,	R =    91.337 deg
};
P[72]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.994  mm,	Y =   728.867  mm,	Z =  1484.009  mm,
	W =   178.600 deg,	P =     1.353 deg,	R =    91.337 deg
};
P[73]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.858  mm,	Y =   734.741  mm,	Z =  1483.870  mm,
	W =   178.606 deg,	P =     1.360 deg,	R =    91.595 deg
};
P[74]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.994  mm,	Y =   728.867  mm,	Z =  1484.009  mm,
	W =   178.600 deg,	P =     1.353 deg,	R =    91.337 deg
};
P[75]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.879  mm,	Y =   721.228  mm,	Z =  1496.190  mm,
	W =   178.600 deg,	P =     1.353 deg,	R =    91.337 deg
};
P[76]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2956.848  mm,	Y =   716.329  mm,	Z =  1502.305  mm,
	W =   178.600 deg,	P =     1.353 deg,	R =    91.337 deg
};
P[77]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2951.545  mm,	Y =   687.386  mm,	Z =  1613.012  mm,
	W =   178.615 deg,	P =     1.332 deg,	R =    91.317 deg
};
P[78]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  2952.272  mm,	Y =   693.817  mm,	Z =  1682.095  mm,
	W =   178.600 deg,	P =     1.354 deg,	R =    91.337 deg
};
/END
