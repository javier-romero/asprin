#!/usr/bin/python

import sys
import yacc
from spec_lexer import Lexer
import ast

# logging
import logging
#logging.basicConfig(filename="q.log", level=logging.DEBUG)

#
# Exception Handling
#
class ParseError(Exception):
    pass

#
#
# Ply Preference Specification Parser
#
#

class Parser(object):

    def __init__(self):
        # start famework
        self.lexer = Lexer()
        self.tokens = self.lexer.tokens
        self.parser = yacc.yacc(module=self)
        self.log = logging.getLogger()
        # semantics
        self.p_statements = 0
        self.list = []

    def __parse_str(self, pref):
        self.element = ast.Element()
        self.parser.parse(pref, self.lexer.lexer, debug=self.log) # parses into self.list
        self.lexer.reset()

    def __print_list(self):
        ast.Statement.underscores = self.get_underscores()
        out = ""
        for i in self.list:
            if i[0] == "CODE":       out += i[1]
            if i[0] == "PREFERENCE": out += i[1].str()
            if i[0] == "OPTIMIZE":   out += i[1].str()
        if ast.PStatement.bfs:
            out += ast.bf_encoding.replace("_",ast.Statement.underscores)
        return out

    #
    # Input:  string
    # Output: string with the translation
    #
    def parse_str(self,str):
        self.__parse_str(str)
        return self.__print_list()

    #
    # Input:  list of files
    # Output: string with the translation
    #
    def parse_files(self,files):
        for i in files:
            if self.list != []: self.list.append(("CODE","\n#program base.\n"))
            self.__parse_str(open(i).read())
        return self.__print_list()

    # return the underscores needed
    def get_underscores(self):
        return "_" + ("_" * self.lexer.underscores)


    #
    # Syntax:
    #   A preference statement has form:
    #     #preference(t1,t2) { E1; ...; En } [ : B ].
    #   where
    #     ti are clingo terms,
    #     Ei are preference elements, and
    #     B is a body of clingo literals.
    #   A preference element has form:
    #     S1 [ >> ... >> Sn ] [ || S0 ] [ : B ]
    #   where
    #     Si is a set with weighted bodies of boolean formulas, or with weighted naming atoms, or with a combination of both.
    #   A weighted body with boolean formulas has form:
    #     [[t] :: ][BF1, ..., BFn]
    #   where BFi is a boolean formula of clingo literals (using 'not', '&', '|', '(' and ')').
    #   A weighted naming atom has form:
    #     [[t] :: ][**A]
    #   where A is a clingo atom.
    #   Weighted elements may not be empty.
    #   An optimize statement has form:
    #     #optimize(t) [ : B ].
    #
    # Minor notes:
    #   (atom)             is not allowed (and never needed :)
    #   bitwise operator & is not allowed (Roland said that this operator will be eliminated from the clingo language)
    #   weighted elements without right-hand-side:
    #     [t] ::
    #   are interpreted as
    #     [t] :: #true
    #
    # Comparison with minimize statements:
    #   asprin accepts boolean formulas
    #   asprin accepts no @ symbol
    #   if there is no COLON, then asprin interprets it as a literal (clingo interprets it as a term)
    #   asprin accepts ' :: ' as an element
    # Basic case: clingo elements of form
    #   t : Body
    # may be written as asprin elements of form
    #   t :: Body
    #

    #
    # START
    #

    precedence = (
        ('left', 'DOTS'),
        ('left', 'XOR'),
        ('left', 'QUESTION'),
        ('left', 'AND'),
        ('left', 'ADD', 'SUB'),
        ('left', 'MUL', 'SLASH', 'MOD'),
        ('right','POW'),
        ('right','POW_NO_WS'),
        ('left', 'UMINUS', 'UBNOT'),
        ('left', 'BFVBAR'),
        ('left', 'BFAND'),
        ('left', 'BFNOT'),
    )

    start = 'program'    # the start symbol in our grammar

    def p_program_1(self,p):
        """ program : program statement
                    |
        """
        pass

    def p_statement_1(self,p):
        """ statement : CODE
        """
        self.list.append(("CODE",p[1]))


    #
    # PREFERENCE STATEMENT
    #

    def p_statement_2(self,p):
        'statement : start_preference end_preference'
        pass

    def p_start_preference_1(self,p):
        """ start_preference : PREFERENCE LPAREN term COMMA term RPAREN LBRACE elem_list RBRACE body
                             | PREFERENCE LPAREN term COMMA term RPAREN LBRACE           RBRACE body
        """
        # create preference statement
        s = ast.PStatement()
        self.p_statements += 1
        s.number = self.p_statements
        s.name     = p[3]
        s.type     = p[5]
        s.elements = p[8] if len(p) == 11 else []
        s.body     = p[len(p)-1]
        self.list.append(("PREFERENCE",s))
        # restart element
        self.element = ast.Element()

    def p_end_preference(self,p):
        """ end_preference : DOT change_state CODE
                           | DOT_EOF
        """
        if len(p) == 4:
            self.list.append(("CODE",p[3]))


    #
    # BODY
    #

    def p_body(self,p):
        """ body : COLON litvec
                 |
        """
        p[0] = None
        if len(p)==3: p[0] = p[2]

    def p_litvec(self,p):
        """ litvec : litvec COMMA         ext_atom
                   | litvec COMMA     NOT ext_atom
                   | litvec COMMA NOT NOT ext_atom
                   | litvec COMMA      csp_literal
                   |                      ext_atom
                   |                  NOT ext_atom
                   |              NOT NOT ext_atom
                   |                   csp_literal
        """
        p[0] = p[1:]
        if len(p)>=4 and p[0][1]==",": p[0][1]=", "

    #
    # PREFERENCE ELEMENTS
    #

    def p_elem_list(self,p):
        """ elem_list : elem_list SEM elem body
                      |               elem body
        """
        # set self.element values & append to elem_list
        if len(p) == 5:
            self.element.sets = p[3][0]
            self.element.cond = p[3][1]
            self.element.body = p[4]
            p[0] = p[1] + [self.element]
        else:
            self.element.sets = p[1][0]
            self.element.cond = p[1][1]
            self.element.body = p[2]
            p[0] = [self.element]
        # restart element
        self.element = ast.Element()

    def p_elem(self,p):
        """ elem : elem_head
                 | elem_head COND weighted_body_set
        """
        if len(p) == 2:
            p[0] = (p[1],[])
        else:
            p[0] = (p[1],p[3])
        self.element.vars     = self.element.all_vars
        self.element.all_vars = set()

    def p_elem_head(self,p):
        """ elem_head : elem_head GTGT weighted_body_set
                      |                weighted_body_set
        """
        if len(p) == 4:
            p[0] = p[1] + [p[3]]
        else:
            p[0] = [p[1]]

    def p_weighted_body_set(self,p):
        """ weighted_body_set : LBRACE weighted_body_vec RBRACE
                              |        weighted_body
        """
        if len(p) == 4:
            p[0] = p[2]
        else:
            p[0] = [p[1]]

    def p_weighted_body_vec(Self,p):
        """ weighted_body_vec : weighted_body_vec SEM weighted_body
                              |                       weighted_body
        """
        if len(p) == 4:
            p[0] = p[1] + [p[3]]
        else:
            p[0] = [p[1]]


    #
    # WEIGHTED BODY
    #

    def p_weighted_body_1(self,p):
        """ weighted_body :                      bfvec_x
        """
        p[0] = ast.WBody(None,p[1])

    def p_weighted_body_2(self,p):
        """ weighted_body :            TWO_COLON
        """
        p[0] = ast.WBody(None,[("ext_atom",["true",["#true"]])])

    def p_weighted_body_3(self,p):
        """ weighted_body : ntermvec_x TWO_COLON bfvec_x
        """
        p[0] = ast.WBody(p[1],p[3])

    def p_weighted_body_4(self,p):
        """ weighted_body :            TWO_COLON bfvec_x
        """
        p[0] = ast.WBody(None,p[2])

    def p_weighted_body_5(self,p):
        """ weighted_body : ntermvec_x TWO_COLON
        """
        p[0] = ast.WBody(p[1],[("ext_atom",["true",["#true"]])])

    def p_weighted_body_6(self,p):
        """ weighted_body :                      POW_NO_WS naming_atom
        """
        p[0] = ast.WBody(None,p[2],True)

    def p_weighted_body_7(self,p):
        """ weighted_body : ntermvec_x TWO_COLON POW_NO_WS naming_atom
        """
        p[0] = ast.WBody(p[1],p[4],True)

    def p_weighted_body_8(self,p):
        """ weighted_body :            TWO_COLON POW_NO_WS naming_atom
        """
        p[0] = ast.WBody(None,p[3],True)

    def p_naming_atom(self,p):
        """ naming_atom : identifier
                        | identifier LPAREN argvec RPAREN
        """
        p[0] = p[1:]
        self.element.names.append(p[0])

    #
    # VECTORS
    #

    def p_ntermvec_x(self,p):
        """ ntermvec_x : atomvec
                       | na_ntermvec
                       | atomvec COMMA na_ntermvec
        """
        p[0] = p[1:]

    def p_atomvec(self,p):
        """ atomvec : atom
                    | atomvec COMMA atom
        """
        p[0] = p[1:]
        if len(p)==4:
            self.atomvec.append(("ext_atom",["atom",p[3]]))
        else:
            self.atomvec = [("ext_atom",["atom",p[1]])]

    def p_na_ntermvec(self,p):
        """ na_ntermvec : na_term
                        | na_term COMMA ntermvec
        """
        p[0] = p[1:]

    #
    #   """ bfvec_x : atomvec
    #               | na_bfvec
    #               | atomvec COMMA na_bfvec
    #   """
    #
    #   p[0] becomes a list
    #
    def p_bfvec_x_1(self,p):
        """ bfvec_x  : atomvec
        """
        p[0] = self.atomvec

    def p_bfvec_x_2(self,p):
        """ bfvec_x  : na_bfvec
        """
        p[0] = p[1]

    def p_bfvec_x_3(self,p):
        """ bfvec_x :  atomvec COMMA na_bfvec
        """
        p[0] = self.atomvec + p[3]

    def p_na_bfvec(self,p):
        """ na_bfvec : na_bformula COMMA bfvec
                     | na_bformula
        """
        if len(p)==4:
            p[0] = [p[1]] + p[3]
        else:
            p[0] = [p[1]]

    def p_bfvec(self,p):
        """ bfvec    : bfvec COMMA bformula
                     |             bformula
        """
        if len(p)==4:
            p[0] = p[1] + [p[3]]
        else:
            p[0] = [p[1]]


    #
    # BOOLEAN FORMULAS
    #

    #
    # using non reachable token NOREACH for making the grammar LALR(1)
    # (atom) is not allowed
    #
    #    """ bformula :               ext_atom
    #                 |            csp_literal
    #                 |         paren_bformula
    #                 | bformula VBAR bformula %prec BFVBAR
    #                 | bformula AND  bformula %prec BFAND
    #                 |          NOT  bformula %prec BFNOT
    #
    #                 | LPAREN     identifier                      NOREACH
    #                 | LPAREN     identifier LPAREN argvec RPAREN NOREACH
    #                 | LPAREN SUB identifier                      NOREACH
    #                 | LPAREN SUB identifier LPAREN argvec RPAREN NOREACH
    #
    #        paren_bformula : LPAREN na_bformula RPAREN
    #
    #        na_bformula :            na_ext_atom
    #                    |            csp_literal
    #                    |         paren_bformula
    #                    | bformula VBAR bformula %prec BFVBAR
    #                    | bformula AND  bformula %prec BFAND
    #                    |          NOT  bformula %prec BFNOT
    #    """

    def p_bformula_1(self,p):
        """ bformula :               ext_atom
        """
        p[0] = p[1]

    def p_bformula_2(self,p):
        """ bformula :            csp_literal
        """
        p[0] = ("csp",[p[1]])

    def p_bformula_3(self,p):
        """ bformula :         paren_bformula
        """
        p[0] = p[1]

    def p_bformula_4(self,p):
        """ bformula : bformula VBAR bformula %prec BFVBAR
        """
        p[0] = ("or",[p[1],p[3]])

    def p_bformula_5(self,p):
        """ bformula : bformula  AND bformula %prec BFAND
        """
        p[0] = ("and",[p[1],p[3]])

    def p_bformula_6(self,p):
        """ bformula :           NOT bformula %prec BFNOT
        """
        p[0] = ("neg",[p[2]])

    # unreachable
    def p_formula_7(self,p):
        """ bformula : LPAREN     identifier                      NOREACH
                     | LPAREN     identifier LPAREN argvec RPAREN NOREACH
                     | LPAREN SUB identifier                      NOREACH
                     | LPAREN SUB identifier LPAREN argvec RPAREN NOREACH
        """
        pass

    def p_paren_formula(self,p):
        """ paren_bformula : LPAREN na_bformula RPAREN
        """
        p[0] = p[2]

    def p_na_bformula_1(self,p):
        """ na_bformula :            na_ext_atom
        """
        p[0] = p[1]

    def p_na_bformula_2(self,p):
        """ na_bformula :            csp_literal
        """
        p[0] = ("csp",[p[1]])

    def p_na_bformula_3(self,p):
        """ na_bformula :         paren_bformula
        """
        p[0] = p[1]

    def p_na_bformula_4(self,p):
        """ na_bformula : bformula VBAR bformula %prec BFVBAR
        """
        p[0] = ("or",[p[1],p[3]])

    def p_na_bformula_5(self,p):
        """ na_bformula : bformula  AND bformula %prec BFAND
        """
        p[0] = ("and",[p[1],p[3]])

    def p_na_bformula_6(self,p):
        """ na_bformula :           NOT bformula %prec BFNOT
        """
        p[0] = ("neg",[p[2]])

    #
    # NOT ATOM TERMS
    #

    def p_na_term(self,p):
        """ na_term : term      DOTS term
                    | term       XOR term
                    | term  QUESTION term
                    | term       ADD term
                    | term       SUB term
                    | term       MUL term
                    | term     SLASH term
                    | term       MOD term
                    | term       POW term
                    | term POW_NO_WS term
                    |            na_term_more
                    | many_minus na_term_more
                    | many_minus SUB identifier LPAREN argvec RPAREN %prec UMINUS
                    | many_minus SUB identifier
        """
        p[0] = p[1:]

    def p_na_term_more(self,p):
        """ na_term_more : BNOT term %prec UBNOT
                         | LPAREN tuplevec RPAREN
                         | AT identifier LPAREN   argvec RPAREN
                         | VBAR unaryargvec VBAR
                         | NUMBER
                         | STRING
                         | INFIMUM
                         | SUPREMUM
                         | variable
                         | ANONYMOUS
        """
        p[0] = p[1:]

    def p_many_minus(self,p):
        """many_minus : SUB
                      | many_minus SUB %prec UMINUS
        """
        p[0] = p[1:]


    #
    # (NOT ATOM) EXTENDED ATOMS
    #
    #   """ ext_atom : TRUE
    #                | FALSE
    #                | atom
    #                | term cmp term
    #   """
    #
    def p_ext_atom_1(self,p):
        """ ext_atom : TRUE
        """
        p[0] = ["ext_atom",["true",["#true"]]]

    def p_ext_atom_2(self,p):
        """ ext_atom : FALSE
        """
        p[0] = ["ext_atom",["false",["#false"]]]

    def p_ext_atom_3(self,p):
        """ ext_atom : atom
        """
        p[0] = ["ext_atom",["atom",p[1]]]

    def p_ext_atom_4(self,p):
        """ ext_atom : term cmp term
        """
        p[0] = ["ext_atom",["cmp",p[1:]]]


    #   """ na_ext_atom : TRUE
    #                   | FALSE
    #                   | term cmp term
    #   """
    def p_na_ext_atom_1(self,p):
        """ na_ext_atom : TRUE
        """
        p[0] = ["ext_atom",["true",["#true"]]]

    def p_na_ext_atom_2(self,p):
        """ na_ext_atom : FALSE
        """
        p[0] = ["ext_atom",["false",["#false"]]]

    def p_na_ext_atom_3(self,p):
        """ na_ext_atom : term cmp term
        """
        p[0] = ["ext_atom",["cmp",p[1:]]]


    #
    # VARIABLES
    #
    def p_variable(self,p):
        """ variable : VARIABLE
        """
        p[0] = p[1]
        self.element.all_vars.add(p[1])

    #
    # GRINGO expressions
    #

    def p_term(self,p):
        """ term : term      DOTS term
                 | term       XOR term
                 | term  QUESTION term
                 | term       ADD term
                 | term       SUB term
                 | term       MUL term
                 | term     SLASH term
                 | term       MOD term
                 | term       POW term
                 | term POW_NO_WS term
                 |            SUB term %prec UMINUS
                 |           BNOT term %prec UBNOT
                 |               LPAREN tuplevec RPAREN
                 |    identifier LPAREN   argvec RPAREN
                 | AT identifier LPAREN   argvec RPAREN
                 | VBAR unaryargvec VBAR
                 | identifier
                 | NUMBER
                 | STRING
                 | INFIMUM
                 | SUPREMUM
                 | variable
                 | ANONYMOUS
        """
        p[0] = p[1:]

    def p_unaryargvec(self,p):
        """ unaryargvec :  term
                        |  unaryargvec SEM term
        """
        p[0] = p[1:]

    def p_ntermvec(self,p):
        """ ntermvec : term
                     | ntermvec COMMA term
        """
        p[0] = p[1:]

    def p_termvec(self,p):
        """ termvec : ntermvec
                    |
        """
        p[0] = p[1:]

    def p_tuple(self,p):
        """ tuple : ntermvec COMMA
                  | ntermvec
                  |          COMMA
                  |
        """
        p[0] = p[1:]

    def p_tuplevec_sem(self,p):
        """ tuplevec_sem :              tuple SEM
                         | tuplevec_sem tuple SEM
        """
        p[0] = p[1:]

    def p_tuplevec(self,p):
        """ tuplevec :              tuple
                     | tuplevec_sem tuple
        """
        p[0] = p[1:]

    def p_argvec(self,p):
        """ argvec :            termvec
                   | argvec SEM termvec
        """
        p[0] = p[1:]

    def p_cmp(self,p):
        """ cmp :  GT
                |  LT
                | GEQ
                | LEQ
                |  EQ
                | NEQ
        """
        p[0] = p[1]

    def p_atom(self,p):
        """ atom :     identifier
                 |     identifier LPAREN argvec RPAREN
                 | SUB identifier
                 | SUB identifier LPAREN argvec RPAREN
        """
        p[0] = p[1:]
        self.element.preds.append(p[0])

    def p_csp_mul_term(self,p):
        """ csp_mul_term : CSP term CSP_MUL term
                         | term CSP_MUL CSP term
                         |              CSP term
                         |                  term
        """
        p[0] = p[1:]

    def p_csp_add_term(self,p):
        """ csp_add_term : csp_add_term CSP_ADD csp_mul_term
                         | csp_add_term CSP_SUB csp_mul_term
                         |                      csp_mul_term
        """
        p[0] = p[1:]

    def p_csp_rel(self,p):
        """ csp_rel : CSP_GT
                    | CSP_LT
                    | CSP_GEQ
                    | CSP_LEQ
                    | CSP_EQ
                    | CSP_NEQ
        """
        p[0] = p[1]

    def p_csp_literal(self,p):
        """ csp_literal : csp_literal   csp_rel csp_add_term
                        | csp_add_term  csp_rel csp_add_term
        """
        p[0] = p[1:]

    def p_identifier(self,p):
        """ identifier : IDENTIFIER
        """
        p[0] = p[1]


    #
    # OPTIMIZE
    #

    def p_statement_3(self,p):
        """ statement : start_optimize end_optimize
        """
        pass

    def p_start_optimize(self,p):
        """ start_optimize : OPTIMIZE LPAREN term RPAREN body
        """
        s = ast.OStatement()
        s.name     = p[3]
        s.body     = p[5]
        self.list.append(("OPTIMIZE",s))

    def p_end_optimize(self,p):
        """ end_optimize : DOT change_state CODE
                         | DOT_EOF
        """
        if len(p) == 4:
            self.list.append(("CODE",p[3]))

    #
    # CHANGE STATE
    #

    def p_change_state(self,p):
        """ change_state :
        """
        p.lexer.pop_state()
        self.lexer.code_start = self.lexer.lexer.lexpos


    #
    # ERROR
    #

    def p_error(self,p):
        print("Syntax error!")
        sys.exit()

#
#
# __main__
#
#

if __name__ == "__main__":

    test = """

% empty
#preference(p,subset) {
    1 :: a(X), -b(X) >> { p ; **rrrr ; 34 :: a(X,Y) & -b(X), d(X,Z) } || 44 :: **q(X) : a;
    2 :: c(X), d(X);
    a(X) & not b(X) | (c(X) & not q(X,Y));
    a , b, c & not d, q | x
} : mya(X), myb(X).

#preference(p,p) { b }.

#preference(a,b) { a(X) >> b(X) : x(X); a(X) >> c(X), #true, X>Y, a&b: x(X) }.

"""
    string = False
    #string = True  # uncomment to test string
    parser = Parser()
    if string:
        print parser.parse_str(test)
        sys.exit()
    print parser.parse_files(sys.argv[1:])

