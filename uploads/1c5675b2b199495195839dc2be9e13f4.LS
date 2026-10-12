/PROG  HOMETOPURGE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "HomToPurge V4.0";
PROG_SIZE	= 834;
CREATE		= DATE 15-02-05  TIME 15:56:40;
MODIFIED	= DATE 21-02-05  TIME 09:14:50;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 17;
MEMORY_SIZE	= 1270;
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
   1:  !**************************** ;
   2:  ! HOME TO PURGE ;
   3:  !**************************** ;
   4:   ;
   5:  MESSAGE[MOVING TO PURGE] ;
   6:   ;
   7:  IF DO[434:At PURGE Pos    ]=ON,JMP LBL[99] ;
   8:   ;
   9:  !Insert motion points to move ;
  10:  !from HOME to PURGE. ;
  11:  UTOOL_NUM=1 ;
  12:  UFRAME_NUM=10 ;
  13:J PR[1:HOME Position] 20% CNT100    ;
  14:J P[2] 20% CNT100    ;
  15:J P[3] 20% CNT100    ;
  16:   ;
  17:  LBL[99] ;
/POS
P[2]{
   GP1:
	UF : 10, UT : 1,	
	J1=   -90.000 deg,	J2=   -40.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=  -180.000 deg,
	E1=   500.000  mm
};
P[3]{
   GP1:
	UF : 10, UT : 1,	
	J1=  -107.977 deg,	J2=    10.898 deg,	J3=   -43.774 deg,
	J4=    16.020 deg,	J5=    75.588 deg,	J6=  -283.000 deg,
	E1=  1000.000  mm
};
/END
