#!/usr/bin/python


#
# DEFINE Predicates
#

PREFERENCE     = "preference" # arity 2 and 5
OPTIMIZE       = "optimize"   # arity 1
HOLDS          = "holds"      # arity 2
SAT            = "sat"        # arity 1
BF             = "bf"         # arity 1
DOM            = "dom"        # arity 1
PREFERENCE_DOM = "pref_dom"   # arity 1



#
# DEFINE Terms
#

TRUE  = "true"
FALSE = "false"
ATOM  = "atom"
CMP   = "cmp"
NEG   = "neg"
AND   = "and"
OR    = "or"
NOT   = "not"
NAME  = "name"
FOR   = "for"



#
# Boolean Formula Definition
#

bf_encoding = """
_sat(and(X,Y)) :- _sat(X), _sat(Y), _bf(and(X,Y)).
_sat(or (X,Y)) :- _sat(X),          _bf(or (X,Y)).
_sat(or (X,Y)) :- _sat(Y),          _bf(or (X,Y)).
_sat(neg(X  )) :- not _sat(X),      _bf(neg(X  )).
_bf(X) :- _bf(and(X,Y)).
_bf(Y) :- _bf(and(X,Y)).
_bf(X) :- _bf(or (X,Y)).
_bf(Y) :- _bf(or (X,Y)).
_bf(X) :- _bf(neg(X  )).
_true.
"""



#
# Global Functions
#


# Translate ast to string
def ast2str(ast):
    out = ""
    if ast == None:         return out
    if isinstance(ast,str): return ast
    for e in ast:
        out += ast2str(e)
    return out


# Translate body to string
def body2str(i):
    out = ""
    if isinstance(i,list) and len(i) > 0:
        if isinstance(i[0],str) and i[0] in { "atom", "true", "false", "cmp" }:
            return ast2str(i[1])
        for j in i:
            out += body2str(j)
    return out



# abstract class for preference and optimize statements
class Statement:

    underscores = ""

    def __init__(self):
        self.number   = None
        self.name     = None
        self.type     = None
        self.elements = []
        self.body     = None



# preference statement
class PStatement(Statement):


    bfs = False # True if there are boolean formulas which are not literals


    def __has_var(self,ast):
        if ast == None:         return False
        if isinstance(ast,str): return (ast[0]>="A" and ast[0]<="Z")
        for e in ast:
            if self.__has_var(e): return True
        return False


    def __create_body(self,preds,names):
        u = Statement.underscores
        preds = set([ ast2str(x) for x in preds if self.__has_var(x) ])
        bodyp = ", ".join([u+DOM+"("+pred+")" for pred in preds])
        names = set([ ast2str(x) for x in names if self.__has_var(x) ])
        bodyn = ", ".join([u+PREFERENCE_DOM+"("+name+")" for name in names])
        if bodyp!="" and bodyn!="": return bodyp + ", " + bodyn
        return bodyp + bodyn

    def __create_body(self,element):
        u = Statement.underscores
        out = []
        for j in element.sets:
            for k in j:
                out += k.get_atoms()
        for k in element.cond:
            out += k.get_atoms()
        return ", ".join(u+DOM+"("+i+")" for i in out)


    def str(self):

        # underscores
        u = Statement.underscores

        # tostring
        name = ast2str(self.name)
        type = ast2str(self.type)

        # pref/2
        statement_body = body2str(self.body) if self.body is not None else ""
        arrow = " :- " if statement_body != "" else ""
        out = u + PREFERENCE + "({},{}){}{}.\n".format(name,type,arrow,statement_body)

        # pref/5
        elem = 1
        for i in self.elements:

            set = 1

            # body
            if i.body is not None:    body = body2str(i.body)
            else:                     body = self.__create_body(i)
            #else:                     body = self.__create_body(i.preds,i.names)
            if statement_body != "":
                if body != "": body += ", "
                body += statement_body
            arrow = " :- " if body != "" else ""

            # head sets
            for j in i.sets:
                for k in j:
                    out += u + PREFERENCE + "({},(({},{}),({})),{},{},{}){}{}.\n".format(
                                name,self.number,elem,",".join(i.vars),set,k.str_body(),k.str_weight(),arrow,body)
                    out += k.str_holds(body)
                    out += k.str_bf   (body)
                    out += k.str_sat  (body)
                    out += "\n"
                set += 1

            # condition set
            for k in i.cond:
                out +=     u + PREFERENCE + "({},(({},{}),({})),{},{},{}){}{}.\n".format(
                                name,self.number,elem,",".join(i.vars),  0,k.str_body(),k.str_weight(),arrow,body)
                out += "\n"

            elem += 1
        #end for

        return out


# optimize statement
class OStatement(Statement):


    def str(self):
        return Statement.underscores + OPTIMIZE + "({}) :- {}.\n".format(ast2str(self.name),body2str(self.body))


# preference element
class Element:


    def __init__(self):
        self.vars  = set()
        self.preds = []
        self.names = []
        self.body  = None
        self.sets  = []
        self.cond  = []
        self.all_vars  = set() # temporary variable



# exception for WBody (should never rise)
class AstException(Exception):
    pass



# weighted body
class WBody:


    def __init__(self,weight,body,naming=False):
        self.weight             = weight
        self.body               = body  # list
        self.naming             = naming
        self.bf                 = None  # reified boolean formula representing the body
        self.ext_atoms_in_bf    = set() # extended atoms appearing in (boolean formulas which are not literals)
        self.analyzed           = False




    def __translate_ext_atom(self,atom):
        if atom[0] == "true":
            return ATOM+"("+Statement.underscores+TRUE+")", Statement.underscores+TRUE
        elif atom[0] == "false":
            return ATOM+"("+Statement.underscores+FALSE+")", Statement.underscores+FALSE
        elif atom[0] == "atom":
            return ATOM+"("+ast2str(atom[1])+")", ast2str(atom[1])
        elif atom[0] == "cmp":
            return CMP+"(\""+atom[1][1]+"\","+ast2str(atom[1][0])+","+ast2str(atom[1][2])+")", ast2str(atom[1])
        else:
            raise AstException


    def __bf2str(self,bf):
        if bf[0] == "ext_atom":
            atom_reified, atom = self.__translate_ext_atom(bf[1])
            self.ext_atoms_in_bf.add((atom_reified,atom))  # fills self.ext_atoms_in_bf
            return atom_reified
        if bf[0]=="neg":
            return NEG+"("  + self.__bf2str(bf[1][0]) + ")"
        if bf[0]=="and":
            return AND+"("  + self.__bf2str(bf[1][0]) + "," + self.__bf2str(bf[1][1]) + ")"
        if bf[0]=="or":
            return OR+"("   + self.__bf2str(bf[1][0]) + "," + self.__bf2str(bf[1][1]) + ")"


    def __translate_lit(self,lit):
        neg  = 0
        while lit[0]=="neg" and neg<=1:
            neg += 1
            lit  = lit[1][0]
        if lit[0]=="ext_atom":
            atom_reified, atom = self.__translate_ext_atom(lit[1])
            return ("lit",(neg*(NEG+"("))+atom_reified+(neg*")"),(neg*(NOT+" "))+atom)
        return None


    def __translate_bf(self,bf):
        out = self.__translate_lit(bf)
        if out is not None: return out
        string = self.__bf2str(bf)              # fills self.ext_atoms_in_bf
        return ("bf",string,Statement.underscores+SAT+"("+string+")")


    #
    # modifies elements of self.body with triples
    #   (type,reified,string)
    # where:
    #   - type may be bf or lit
    #   - reified is what will be used to write for()
    #   - string  is what will be used to generate holds/2
    # it also fills self.ext_atoms_in_bf with the atoms appearing in the body
    # and     fills self.bf     with the reified version of the body
    #
    def __analyze_body(self):
        # translate body
        for i in range(len(self.body)):
            self.body[i] = self.__translate_bf(self.body[i]) # fills self.ext_atoms_in_bf
        # fill self.bf the
        self.bf  = "".join([AND+"("+x[1]+"," for x in self.body[:-1]])
        self.bf += self.body[-1][1]
        self.bf += "".join([")"             for x in self.body[:-1]])
        self.analyzed = True


    #
    # FUNCTIONS RETURNING STRINGS
    #


    # return the weight
    def str_weight(self):
        return ast2str(self.weight) if self.weight is not None else "()"


    # return the body with for() or name()
    def str_body(self):
        if self.naming: return NAME+"({})".format(ast2str(self.body))
        if not self.analyzed: self.__analyze_body()
        return FOR+"({})".format(self.bf)


    # return rules for holds/2
    def str_holds(self,body):
        if self.naming: return ""
        if not self.analyzed: self.__analyze_body()
        if body != "": body = ", " + body
        return Statement.underscores + HOLDS + "(" + str(self.bf) + ",0) :- " + ", ".join([x[2] for x in self.body]) + body + ".\n"


    # return rules for bf/1 with the boolean formulas which are not literals
    # sets PStatement.bfs to True when necessary
    def str_bf(self,body):
        if self.naming: return ""
        if body != "": body = " :- " + body
        bfs = [Statement.underscores + BF + "(" + x[1] + ")" + body + "." for x in self.body if x[0]=="bf"]
        if bfs!=[]:
            PStatement.bfs = True
            return "\n".join(bfs)+"\n"
        return ""


    # return rules for sat/1 with extended atoms appearing in (boolean formulas which are not literals)
    def str_sat(self,body):
        if self.naming:       return ""
        if len(self.ext_atoms_in_bf) == 0: return ""
        if body != "": body = ", " + body
        return "\n".join([Statement.underscores + SAT + "(" + x[0] + ") :- " + x[1] + body + "." for x in self.ext_atoms_in_bf]) + "\n"


    #
    # OTHERS
    #


    def __get_atoms_from_bf(self,bf):
        if bf[0] == "ext_atom":
            return [ast2str(bf[1][1])] if bf[1][0] == "atom" else []
        elif bf[0] == "and" or bf[0] == "or":
            return self.__get_atoms_from_bf(bf[1][0]) + self.__get_atoms_from_bf(bf[1][1])
        elif bf[0] == "neg":
            return self.__get_atoms_from_bf(bf[1][0])


    # return the atoms in the body as a list of strings (called before str_ functions)
    def get_atoms(self):
        out = []
        for i in self.body:
            out += self.__get_atoms_from_bf(i)
        return out



