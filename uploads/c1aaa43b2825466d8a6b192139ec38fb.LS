/PROG  STYLE25
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "SfTstBrkChk V4.1";
PROG_SIZE	= 996;
CREATE		= DATE 14-04-08  TIME 14:51:54;
MODIFIED	= DATE 20-02-27  TIME 12:20:24;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 45;
MEMORY_SIZE	= 1472;
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
/MN
   1:  !************************* ;
   2:  !STYLE 25 ZDT SELF TEST ;
   3:  ! and Brakecheck ;
   4:  !************************* ;
   5:   ;
   6:  !ECHO STYLE AND OPTION ;
   7:  GO[1:ManualStyle]=25 ;
   8:  ECHO OPTION    ;
   9:   ;
  10:  !IF option A run ZDT self test ;
  11:  IF DI[20:OptionBitA]=ON,JMP LBL[10] ;
  12:   ;
  13:  SET SEGMENT(8) ;
  14:  CALL BRAKECHK    ;
  15:   ;
  16:  R[400:Brake Test CNT]=R[400:Brake Test CNT]+1    ;
  17:   ;
  18:  JMP LBL[99] ;
  19:   ;
  20:  LBL[10:Skip BRKCHK] ;
  21:  SET SEGMENT(60) ;
  22:  !Check for Tool Changer ;
  23:  !CALL CKDNETND(55,38) ;
  24:  CALL CKENETND(55,38) ;
  25:   ;
  26:  IF R[38:Node Present]=0,JMP LBL[20] ;
  27:  IF GI[15:Offset P]>0,JMP LBL[25] ;
  28:   ;
  29:  LBL[20:ZDT Test] ;
  30:  CALL DIAG1    ;
  31:   ;
  32:  JMP LBL[99] ;
  33:   ;
  34:  LBL[25:TOOL ON ROBOT] ;
  35:  MESSAGE[Test Stopped] ;
  36:  MESSAGE[Tool is Present] ;
  37:  MESSAGE[Dropoff Tool(x) then Re-Test] ;
  38:  GO[1:ManualStyle]=0 ;
  39:  GO[3:PathSegment]=0 ;
  40:  ABORT ;
  41:   ;
  42:  LBL[99] ;
  43:  MOVE TO HOME    ;
  44:  GO[1:ManualStyle]=0 ;
  45:  GO[3:PathSegment]=0 ;
/POS
/END
