/PROG  BRAKECHK	  Macro
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "BrakeChk V4.0";
PROG_SIZE	= 978;
CREATE		= DATE 19-11-06  TIME 10:02:56;
MODIFIED	= DATE 20-02-27  TIME 12:20:20;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 28;
MEMORY_SIZE	= 1434;
PROTECT		= READ_WRITE;
TCD:  STACK_SIZE	= 0,
      TASK_PRIORITY	= 50,
      TIME_SLICE	= 0,
      BUSY_LAMP_OFF	= 0,
      ABORT_REQUEST	= 0,
      PAUSE_REQUEST	= 0;
DEFAULT_GROUP	= *,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
/APPL
  SPOT Welding Equipment Number : 1 ;
/MN
   1:  !************************* ;
   2:  !BrakeCheck V4.0 ;
   3:  !FAULT only, no user prompt ;
   4:  !************************* ;
   5:   ;
   6:  R[399:Brake Jx Fail]=0    ;
   7:  IF SO[7:TP enabled]=ON,JMP LBL[99] ;
   8:  !Start Test ;
   9:  $BCCFG.$BCK_START=1 ;
  10:  !Test Complete ;
  11:  WAIT $BCCFG.$BCK_START=0    ;
  12:  !Check J1,J2 ;
  13:  IF ($BCK_GRP[1].$CHK_RESULT[1]=1 OR $BCK_GRP[1].$CHK_RESULT[2]=1) THEN ;
  14:  R[399:Brake Jx Fail]=1    ;
  15:  ENDIF ;
  16:  !Check J3,J4 ;
  17:  IF ($BCK_GRP[1].$CHK_RESULT[3]=1 OR $BCK_GRP[1].$CHK_RESULT[4]=1) THEN ;
  18:  R[399:Brake Jx Fail]=1    ;
  19:  ENDIF ;
  20:  !Check J5,J6 ;
  21:  IF ($BCK_GRP[1].$CHK_RESULT[5]=1 OR $BCK_GRP[1].$CHK_RESULT[6]=1) THEN ;
  22:  R[399:Brake Jx Fail]=1    ;
  23:  ENDIF ;
  24:  IF (R[399:Brake Jx Fail]=1) THEN ;
  25:  UALM[3] ;
  26:  ENDIF ;
  27:   ;
  28:  LBL[99] ;
/POS
/END
