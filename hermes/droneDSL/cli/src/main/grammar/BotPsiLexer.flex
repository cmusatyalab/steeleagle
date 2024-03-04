package org.droneDSL.cli.parser;

import com.intellij.lexer.FlexLexer;
import com.intellij.psi.tree.IElementType;

import static com.intellij.psi.TokenType.BAD_CHARACTER;
import static com.intellij.psi.TokenType.WHITE_SPACE;
import static org.droneDSL.cli.parser.BotPsiElementTypes.*;
%%

%{
  public _BotPsiLexer() {
    this((java.io.Reader)null);
  }
%}

%public
%class _BotPsiLexer
%implements FlexLexer
%function advance
%type IElementType
%unicode

EOL=\R
WHITE_SPACE=\s+

NUMBER=-?[0-9]+(\.[0-9]+)?
IDENTIFIER=[α-ωa-zA-Z_][α-ωa-zA-Z0-9_'-]*
//  SelfAdaptive        { return MISSION_SELFADAPTIVE_KW; }
%%
<YYINITIAL> {
  {WHITE_SPACE}       { return WHITE_SPACE; }
  {NUMBER}            { return NUMBER; }
  Task                { return TASK_KW; }
  Detect              { return TASK_DETECT_KW; }
  Track               { return TASK_TRACK_KW; }
  Mission             { return MISSION_KW; }
  Transition          { return TRANSITION_KW; }
  Start               { return MISSION_START_KW; }
  {IDENTIFIER}        { return ID; }
  "{"                 { return LBRACE; }
  "}"                 { return RBRACE; }
  "("                 { return LPAREN; }
  ")"                 { return RPAREN; }
  "["                 { return LSQUA; }
  "]"                 { return RSQUA; }
  ","                 { return COMMA; }
  ":"                 { return COLON; }
  "->"                { return ARROW; }
  "<"                 { return LANGL; }
  ">"                 { return RANGL; }
}

[^] { return BAD_CHARACTER; }
