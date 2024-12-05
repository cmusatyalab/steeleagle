// This is a generated file. Not intended for manual editing.
package org.droneDSL.compile.parser;

import com.intellij.lang.PsiBuilder;
import com.intellij.lang.PsiBuilder.Marker;
import static org.droneDSL.compile.parser.BotPsiElementTypes.*;
import static com.intellij.lang.parser.GeneratedParserUtilBase.*;
import com.intellij.psi.tree.IElementType;
import com.intellij.lang.ASTNode;
import com.intellij.psi.tree.TokenSet;
import com.intellij.lang.PsiParser;
import com.intellij.lang.LightPsiParser;

@SuppressWarnings({"SimplifiableIfStatement", "UnusedAssignment"})
public class BotPsiParser implements PsiParser, LightPsiParser {

  public ASTNode parse(IElementType t, PsiBuilder b) {
    parseLight(t, b);
    return b.getTreeBuilt();
  }

  public void parseLight(IElementType t, PsiBuilder b) {
    boolean r;
    b = adapt_builder_(t, b, this, null);
    Marker m = enter_section_(b, 0, _COLLAPSE_, null);
    r = parse_root_(t, b);
    exit_section_(b, 0, m, t, r, true, TRUE_CONDITION);
  }

  protected boolean parse_root_(IElementType t, PsiBuilder b) {
    return parse_root_(t, b, 0);
  }

  static boolean parse_root_(IElementType t, PsiBuilder b, int l) {
    return file(b, l + 1);
  }

  /* ********************************************************** */
  // LANGL <<param>> RANGL
  public static boolean angle_bracked(PsiBuilder b, int l, Parser _param) {
    if (!recursion_guard_(b, l, "angle_bracked")) return false;
    if (!nextTokenIs(b, LANGL)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, LANGL);
    r = r && _param.parse(b, l);
    r = r && consumeToken(b, RANGL);
    exit_section_(b, m, ANGLE_BRACKED, r);
    return r;
  }

  /* ********************************************************** */
  // ID <<coloned attribute_expr>>
  public static boolean attribute(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "attribute")) return false;
    if (!nextTokenIs(b, ID)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, ID);
    r = r && coloned(b, l + 1, BotPsiParser::attribute_expr);
    exit_section_(b, m, ATTRIBUTE, r);
    return r;
  }

  /* ********************************************************** */
  // NUMBER | name | <<square_bracked <<commaSep <<paren tuple>> >> >> | <<angle_bracked name>> | <<paren tuple>>
  public static boolean attribute_expr(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "attribute_expr")) return false;
    boolean r;
    Marker m = enter_section_(b, l, _NONE_, ATTRIBUTE_EXPR, "<attribute expr>");
    r = consumeToken(b, NUMBER);
    if (!r) r = name(b, l + 1);
    if (!r) r = square_bracked(b, l + 1, attribute_expr_2_0_parser_);
    if (!r) r = angle_bracked(b, l + 1, BotPsiParser::name);
    if (!r) r = paren(b, l + 1, BotPsiParser::tuple);
    exit_section_(b, l, m, r, false, null);
    return r;
  }

  /* ********************************************************** */
  // attribute*
  static boolean attributes(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "attributes")) return false;
    while (true) {
      int c = current_position_(b);
      if (!attribute(b, l + 1)) break;
      if (!empty_element_parsed_guard_(b, "attributes", c)) break;
    }
    return true;
  }

  /* ********************************************************** */
  // LBRACE <<param>> RBRACE
  static boolean braced(PsiBuilder b, int l, Parser _param) {
    if (!recursion_guard_(b, l, "braced")) return false;
    if (!nextTokenIs(b, LBRACE)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, LBRACE);
    r = r && _param.parse(b, l);
    r = r && consumeToken(b, RBRACE);
    exit_section_(b, m, null, r);
    return r;
  }

  /* ********************************************************** */
  // COLON <<param>>
  static boolean coloned(PsiBuilder b, int l, Parser _param) {
    if (!recursion_guard_(b, l, "coloned")) return false;
    if (!nextTokenIs(b, COLON)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, COLON);
    r = r && _param.parse(b, l);
    exit_section_(b, m, null, r);
    return r;
  }

  /* ********************************************************** */
  static Parser commaSep_$(Parser _param) {
    return (b, l) -> commaSep(b, l + 1, _param);
  }

  // <<param>> (COMMA <<param>>) *
  static boolean commaSep(PsiBuilder b, int l, Parser _param) {
    if (!recursion_guard_(b, l, "commaSep")) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = _param.parse(b, l);
    r = r && commaSep_1(b, l + 1, _param);
    exit_section_(b, m, null, r);
    return r;
  }

  // (COMMA <<param>>) *
  private static boolean commaSep_1(PsiBuilder b, int l, Parser _param) {
    if (!recursion_guard_(b, l, "commaSep_1")) return false;
    while (true) {
      int c = current_position_(b);
      if (!commaSep_1_0(b, l + 1, _param)) break;
      if (!empty_element_parsed_guard_(b, "commaSep_1", c)) break;
    }
    return true;
  }

  // COMMA <<param>>
  private static boolean commaSep_1_0(PsiBuilder b, int l, Parser _param) {
    if (!recursion_guard_(b, l, "commaSep_1_0")) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, COMMA);
    r = r && _param.parse(b, l);
    exit_section_(b, m, null, r);
    return r;
  }

  /* ********************************************************** */
  // ID <<paren (NUMBER | ID) >>?
  public static boolean cond(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "cond")) return false;
    if (!nextTokenIs(b, ID)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, ID);
    r = r && cond_1(b, l + 1);
    exit_section_(b, m, COND, r);
    return r;
  }

  // <<paren (NUMBER | ID) >>?
  private static boolean cond_1(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "cond_1")) return false;
    paren(b, l + 1, BotPsiParser::cond_1_0_0);
    return true;
  }

  // NUMBER | ID
  private static boolean cond_1_0_0(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "cond_1_0_0")) return false;
    boolean r;
    r = consumeToken(b, NUMBER);
    if (!r) r = consumeToken(b, ID);
    return r;
  }

  /* ********************************************************** */
  // task mission
  static boolean file(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "file")) return false;
    if (!nextTokenIs(b, TASK_KW)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = task(b, l + 1);
    r = r && mission(b, l + 1);
    exit_section_(b, m, null, r);
    return r;
  }

  /* ********************************************************** */
  // MISSION_KW <<braced mission_content>>
  public static boolean mission(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "mission")) return false;
    if (!nextTokenIs(b, MISSION_KW)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, MISSION_KW);
    r = r && braced(b, l + 1, BotPsiParser::mission_content);
    exit_section_(b, m, MISSION, r);
    return r;
  }

  /* ********************************************************** */
  // mission_start_decl mission_transition*
  public static boolean mission_content(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "mission_content")) return false;
    if (!nextTokenIs(b, MISSION_START_KW)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = mission_start_decl(b, l + 1);
    r = r && mission_content_1(b, l + 1);
    exit_section_(b, m, MISSION_CONTENT, r);
    return r;
  }

  // mission_transition*
  private static boolean mission_content_1(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "mission_content_1")) return false;
    while (true) {
      int c = current_position_(b);
      if (!mission_transition(b, l + 1)) break;
      if (!empty_element_parsed_guard_(b, "mission_content_1", c)) break;
    }
    return true;
  }

  /* ********************************************************** */
  // MISSION_START_KW task_name
  public static boolean mission_start_decl(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "mission_start_decl")) return false;
    if (!nextTokenIs(b, MISSION_START_KW)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, MISSION_START_KW);
    r = r && task_name(b, l + 1);
    exit_section_(b, m, MISSION_START_DECL, r);
    return r;
  }

  /* ********************************************************** */
  // TRANSITION_KW <<paren cond>> task_name ARROW task_name
  public static boolean mission_transition(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "mission_transition")) return false;
    if (!nextTokenIs(b, TRANSITION_KW)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, TRANSITION_KW);
    r = r && paren(b, l + 1, BotPsiParser::cond);
    r = r && task_name(b, l + 1);
    r = r && consumeToken(b, ARROW);
    r = r && task_name(b, l + 1);
    exit_section_(b, m, MISSION_TRANSITION, r);
    return r;
  }

  /* ********************************************************** */
  // ID
  public static boolean name(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "name")) return false;
    if (!nextTokenIs(b, ID)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, ID);
    exit_section_(b, m, NAME, r);
    return r;
  }

  /* ********************************************************** */
  static Parser paren_$(Parser _param) {
    return (b, l) -> paren(b, l + 1, _param);
  }

  // LPAREN <<param>> RPAREN
  public static boolean paren(PsiBuilder b, int l, Parser _param) {
    if (!recursion_guard_(b, l, "paren")) return false;
    if (!nextTokenIs(b, LPAREN)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, LPAREN);
    r = r && _param.parse(b, l);
    r = r && consumeToken(b, RPAREN);
    exit_section_(b, m, PAREN, r);
    return r;
  }

  /* ********************************************************** */
  // LSQUA <<param>> RSQUA
  public static boolean square_bracked(PsiBuilder b, int l, Parser _param) {
    if (!recursion_guard_(b, l, "square_bracked")) return false;
    if (!nextTokenIs(b, LSQUA)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, LSQUA);
    r = r && _param.parse(b, l);
    r = r && consumeToken(b, RSQUA);
    exit_section_(b, m, SQUARE_BRACKED, r);
    return r;
  }

  /* ********************************************************** */
  // TASK_KW <<braced task_decl*>>
  public static boolean task(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "task")) return false;
    if (!nextTokenIs(b, TASK_KW)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeToken(b, TASK_KW);
    r = r && braced(b, l + 1, BotPsiParser::task_1_0);
    exit_section_(b, m, TASK, r);
    return r;
  }

  // task_decl*
  private static boolean task_1_0(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "task_1_0")) return false;
    while (true) {
      int c = current_position_(b);
      if (!task_decl(b, l + 1)) break;
      if (!empty_element_parsed_guard_(b, "task_1_0", c)) break;
    }
    return true;
  }

  /* ********************************************************** */
  // <<braced <<commaSep attributes>>>>
  public static boolean task_body(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "task_body")) return false;
    if (!nextTokenIs(b, LBRACE)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = braced(b, l + 1, task_body_0_0_parser_);
    exit_section_(b, m, TASK_BODY, r);
    return r;
  }

  /* ********************************************************** */
  // (TASK_DETECT_KW | TASK_TRACK_KW | TASK_AVOID_KW| TASK_TEST_KW) task_name task_body
  public static boolean task_decl(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "task_decl")) return false;
    boolean r;
    Marker m = enter_section_(b, l, _NONE_, TASK_DECL, "<task decl>");
    r = task_decl_0(b, l + 1);
    r = r && task_name(b, l + 1);
    r = r && task_body(b, l + 1);
    exit_section_(b, l, m, r, false, null);
    return r;
  }

  // TASK_DETECT_KW | TASK_TRACK_KW | TASK_AVOID_KW| TASK_TEST_KW
  private static boolean task_decl_0(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "task_decl_0")) return false;
    boolean r;
    r = consumeToken(b, TASK_DETECT_KW);
    if (!r) r = consumeToken(b, TASK_TRACK_KW);
    if (!r) r = consumeToken(b, TASK_AVOID_KW);
    if (!r) r = consumeToken(b, TASK_TEST_KW);
    return r;
  }

  /* ********************************************************** */
  // name
  public static boolean task_name(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "task_name")) return false;
    if (!nextTokenIs(b, ID)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = name(b, l + 1);
    exit_section_(b, m, TASK_NAME, r);
    return r;
  }

  /* ********************************************************** */
  // NUMBER COMMA NUMBER COMMA NUMBER
  public static boolean tuple(PsiBuilder b, int l) {
    if (!recursion_guard_(b, l, "tuple")) return false;
    if (!nextTokenIs(b, NUMBER)) return false;
    boolean r;
    Marker m = enter_section_(b);
    r = consumeTokens(b, 0, NUMBER, COMMA, NUMBER, COMMA, NUMBER);
    exit_section_(b, m, TUPLE, r);
    return r;
  }

  private static final Parser attribute_expr_2_0_0_parser_ = paren_$(BotPsiParser::tuple);
  private static final Parser attribute_expr_2_0_parser_ = commaSep_$(attribute_expr_2_0_0_parser_);
  private static final Parser task_body_0_0_parser_ = commaSep_$(BotPsiParser::attributes);
}
