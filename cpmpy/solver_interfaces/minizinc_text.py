#!/usr/bin/env python
#-*- coding:utf-8 -*-
##
## minizinc_text.py
##
"""
    ===============
    List of classes
    ===============

    .. autosummary::
        :nosignatures:

        MiniZincText

    ==================
    Module description
    ==================

    ==============
    Module details
    ==============
"""

from ..model_tools.get_variables import get_variables
from .solver_interface import SolverInterface
from ..variables import *
from ..expressions import *
import numpy as np

# translate expression tree to MiniZinc textual model
class MiniZincText(SolverInterface):
    # does not do solving itself (you can subclass it)
    # does provide conversion to text model
    def __init__(self):
        self.name = "minizinc_text"

    def supported(self):
        return True # always possible

    def solve(self, model):
        print(self.convert(model))

    def convert(self, model):
        modelvars = get_variables(model)
        txt_vars = "% Generated by CPMpy\ninclude \"globals.mzn\";\n\n"
        for var in modelvars:
            if isinstance(var, BoolVarImpl):
                txt_vars += "var bool: BV{};\n".format(var.name)
            elif isinstance(var, IntVarImpl):
                txt_vars += "var {}..{}: IV{};\n".format(var.lb, var.ub, var.name)

        txt_cons = ""
        for con in model.constraints:
            txt_cons += "constraint {};\n".format(self.convert_expression(con))

        txt_obj = "solve "
        if model.objective is None:
            txt_obj += "satisfy;"
        else:
            if model.objective_max:
                txt_obj += "maximize "
            else:
                txt_obj += "minimize "
            txt_obj += "{};\n".format(self.convert_expression(model.objective))
                
        return txt_vars+"\n"+txt_cons+txt_obj

    # expected to return a string
    def convert_expression(self, expr):
        if is_any_list(expr):
            if isinstance(expr, np.ndarray):
                # must flatten
                expr_str = [self.convert_expression(e) for e in expr.flat]
            else:
                expr_str = [self.convert_expression(e) for e in expr]
            return "[{}]".format(",".join(expr_str))

        if not isinstance(expr, Expression) or \
           isinstance(expr, NumVarImpl):
            if expr is True:
                return "true"
            if expr is False:
                return "false"
            # default
            return str(expr)
        
        args_str = [self.convert_expression(e) for e in expr.args]

        # standard expressions: comparison, operator, element
        if isinstance(expr, Comparison):
            # pretty printing: add () if nested comp/op
            for e in expr.args:
                if isinstance(e, (Comparison,Operator)):
                    for i in [0,1]:
                        args_str[i] = "({})".format(args_str[i])
            # infix notation
            return "{} {} {}".format(args_str[0], expr.name, args_str[1])

        if isinstance(expr, Operator):
            # some names differently (the infix names!)
            printmap = {'and': '/\\', 'or': '\\/',
                        'sum': '+', 'sub': '-',
                        'mul': '*', 'div': '/', 'pow': '^'}
            op_str = expr.name
            if op_str in printmap:
                op_str = printmap[op_str]

            # TODO: pretty printing of () as in Operator?

            # special case: unary -
            if self.name == '-':
                return "-{}".format(args_str[0])

            # special case, infix: two args
            if len(args_str) == 2:
                for i,arg_str in enumerate(args_str):
                    if isinstance(expr.args[i], Expression):
                        args_str[i] = "("+args_str[i]+")"
                return "{} {} {}".format(args_str[0], op_str, args_str[1])

            # special case: n-ary (non-binary): rename operator
            printnary = {'and': 'forall', 'or': 'exists', 'xor': 'xorall', 'sum': 'sum'}
            if expr.name in printnary:
                op_str = printnary[expr.name]
                return "{}([{}])".format(op_str, ",".join(args_str))

            # default: prefix printing
            return "{}({})".format(op_str, ",".join(args_str))

        if isinstance(expr, Element):
            subtype = "int"
            # TODO: need better bool check... is_bool() or type()?
            if all((v == 1) is v for v in iter(expr.args[0])):
                subtype = "bool"
            # minizinc is offset 1, which can be problematic for element...
            idx = args_str[1]
            if isinstance(expr.args[1], IntVarImpl) and expr.args[1].lb == 0:
                idx = "{}+1".format(idx)
            # almost there
            txt  = "\n    let {{ array[int] of var {}: arr={} }} in\n".format(subtype, args_str[0])
            txt += f"      arr[{idx}]"
            return txt
        
        # rest: global constraints
        if expr.name.endswith('circuit'): # circuit, subcircuit
            # minizinc is offset 1, which can be problematic here...
            if any(isinstance(e, IntVarImpl) and e.lb == 0 for e in expr.args):
                # redo args_str[0]
                args_str = ["{}+1".format(self.convert_expression(e)) for e in expr.args]
        

        # default
        return "{}([{}])".format(expr.name, ",".join(args_str))
