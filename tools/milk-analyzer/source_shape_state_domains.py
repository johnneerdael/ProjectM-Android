"""Conditional nominal induction for private custom-shape state.

Exact rational interval partitioning checks initialization and one complete
ordered instance transition. Abstract box proposals are never accepted without
an independent closure check. No frame execution or native arithmetic credit.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import re

from equation_loading import select_equation
from scene_equations import Q, READONLY, SHAPE, T, _scalar, source_settings
from source_proofs_worker import domains, export_span, rational, span_op

POLICY = 'source-shape-private-state-induction-v1'
ZERO_POLICY = 'native-new-private-locals-zero-v1'
MAX_NODES = 4096
MAX_DEPTH = 48
DIVISION_EPSILON = rational(.00001)
# Unsupported numerical functions remain unknown in their own dependencies.
# Memory, loops and unknown effects are rejected for the whole shape program.
PURE_UNKNOWN = {'tan','asin','acos','atan','atan2','sqrt','pow','exp','log','log10',
                'int','floor','ceil','sign','rand','sigmoid','sqr','_mod','equal',
                'bnot','band','bor','logistic'}
OPS = {'_add':'add','_sub':'subtract','_mul':'multiply','_neg':'negate',
       'abs':'abs','min':'min','max':'max'}
RESET = set(SHAPE) | set(READONLY) | set(Q) | set(T) | {'instance','thick'}


@dataclass(frozen=True)
class Value:
    span: tuple | None = None
    real_defined: bool = True
    inputs: frozenset = frozenset()


def _join(values):
    if any(not v.real_defined for v in values):
        return Value(None, False, frozenset().union(*(v.inputs for v in values)))
    span = None if any(v.span is None for v in values) else (
        min(v.span[0] for v in values), max(v.span[1] for v in values))
    return Value(span, True, frozenset().union(*(v.inputs for v in values)))


def _validate(tree):
    from effect_families import _EEL
    names, assigned = set(), set()
    count = 0
    def visit(node, depth=0):
        nonlocal count
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError('shape state proof source budget exceeded')
        kind = node.get('kind')
        if kind == 'variable':
            name = node['name'].lower()
            if re.fullmatch(r'reg[0-9]{2}', name):
                raise ValueError('shared registers require cross-phase proof')
            names.add(name)
            return
        if kind == 'constant':
            rational(node['value'])
            return
        name = node.get('function')
        args = node.get('args', [])
        if kind != 'call' or name not in set(OPS) | PURE_UNKNOWN | {
                'sequence','assign','_if','_div','sin','cos','above','below','exec2','exec3'}:
            raise ValueError('unsupported shape storage/control effect: ' + str(name))
        if name == 'sequence':
            if args:raise ValueError('invalid sequence arguments')
            for child in node.get('instructions', []):visit(child, depth+1)
            return
        if node.get('instructions'):raise ValueError('unsupported nested instructions')
        # Native numerical/comparison operands can retain pointers into variable
        # storage while subsequent operands overwrite it. The value interpreter
        # cannot substitute snapshots across those aliases. Keep writes only at
        # the separately modeled ordered assignment/sequence/branch boundaries.
        if name not in {'assign','_if','exec2','exec3'} and _EEL.assignment_targets(args):
            raise ValueError('native expression reference aliases require separate interpretation')
        expected = {'assign':2,'_if':3,'_div':2,'sin':1,'cos':1,'above':2,'below':2,
                    '_neg':1,'abs':1,'min':2,'max':2,'_add':2,'_sub':2,'_mul':2,
                    'exec2':2,'exec3':3}.get(name)
        if expected is not None and len(args) != expected:
            raise ValueError('invalid source operation arity')
        if name == 'assign':
            if args[0].get('kind') != 'variable':raise ValueError('scalar variable assignment required')
            assigned.add(args[0]['name'].lower())
        for child in args:visit(child, depth+1)
    if tree is not None:visit(tree)
    return names, assigned


class Interpreter:
    def __init__(self):
        self.unresolved_operations = set()
        self.finite_inputs = set()
        self.steps = 0

    def execute(self, tree, state):
        self.steps = 0
        if tree is not None:self.value(tree, state)
        return state

    def value(self, node, state, depth=0):
        self.steps += 1
        if self.steps > MAX_NODES*4 or depth > MAX_DEPTH:
            raise ValueError('shape state proof branch budget exceeded')
        kind = node.get('kind')
        if kind == 'constant':
            value = rational(node['value'])
            return Value((value,value))
        if kind == 'variable':return state.get(node['name'].lower(), Value())
        name = node['function']; args = node.get('args', [])
        if name in {'sequence','exec2','exec3'}:
            result = Value((Fraction(0),Fraction(0)))
            for child in node.get('instructions', []) if name=='sequence' else args:
                result = self.value(child, state, depth+1)
            return result
        if name == 'assign':
            result = self.value(args[1],state,depth+1)
            state[args[0]['name'].lower()] = result
            return result
        if name == '_if':return self.branch(args,state,depth)
        children = [self.value(a,state,depth+1) for a in args]
        inputs = frozenset().union(*(v.inputs for v in children))
        if any(not v.real_defined for v in children):return Value(None,False,inputs)
        if name in {'sin','cos'}:
            self.finite_inputs.update(inputs)
            self.unresolved_operations.add(name+' native argument/intermediate finiteness and library arithmetic')
            return Value((Fraction(-1),Fraction(1)),True,inputs)
        if name in {'above','below'}:
            span = (Fraction(0),Fraction(1))
            a,b = children
            if a.span is not None and b.span is not None:
                if name=='above':
                    if a.span[0]>b.span[1]:span=(Fraction(1),Fraction(1))
                    elif a.span[1]<=b.span[0]:span=(Fraction(0),Fraction(0))
                else:
                    if a.span[1]<b.span[0]:span=(Fraction(1),Fraction(1))
                    elif a.span[0]>=b.span[1]:span=(Fraction(0),Fraction(0))
            return Value(span,True,inputs)
        if name in PURE_UNKNOWN:
            self.unresolved_operations.add('unsupported numerical operation: '+name)
            return Value(None,False,inputs)
        if name=='_div':
            denominator=children[1].span
            if denominator is not None and -DIVISION_EPSILON<denominator[0]<=denominator[1]<DIVISION_EPSILON:
                # Source34 div returns exactly zero in the open epsilon region,
                # including division by zero. Both operands were still visited.
                return Value((Fraction(0),Fraction(0)),True,inputs)
            if denominator is None or not (denominator[0]>=DIVISION_EPSILON or denominator[1]<=-DIVISION_EPSILON):
                self.unresolved_operations.add('unproved native denominator epsilon seam')
                return Value(None,False,inputs)
            if children[0].span is None:return Value(None,True,inputs)
            reciprocals=(1/denominator[1],1/denominator[0])
            span=span_op('multiply',[children[0].span,reciprocals])
        elif any(v.span is None for v in children):return Value(None,True,inputs)
        else:span=span_op(OPS[name],[v.span for v in children])
        export_span(span)  # Preserve intermediate representability before later cancellation.
        return Value(span,True,inputs)

    def branch(self,args,state,depth):
        condition=self.value(args[0],state,depth+1)
        if not condition.real_defined:
            # Still inspect/merge both branches: effects cannot disappear behind
            # an unsupported numerical condition.
            copies=[dict(state),dict(state)]
            results=[self.value(args[i+1],copies[i],depth+1) for i in range(2)]
            for name in set().union(*(s.keys() for s in copies)):
                if any(s.get(name,Value())!=state.get(name,Value()) for s in copies):
                    state[name]=Value(None,False)
            return Value(None,False,frozenset().union(*(v.inputs for v in results)))
        choices=[]
        if condition.span is None or condition.span!=(0,0):choices.append(True)
        if condition.span is None or condition.span[0]<=0<=condition.span[1]:choices.append(False)
        copies=[];results=[]
        for truth in choices:
            branch=dict(state)
            if not self.refine(args[0],branch,truth):continue
            results.append(self.value(args[1 if truth else 2],branch,depth+1))
            copies.append(branch)
        if not copies:raise ValueError('infeasible branch partition')
        for name in set().union(*(s.keys() for s in copies)):
            state[name]=_join([s.get(name,Value()) for s in copies])
        return _join(results)

    def refine(self,condition,state,truth):
        """Close strict endpoints conservatively; never discard equality cases."""
        name=condition.get('function');args=condition.get('args',[])
        if name not in {'above','below'} or len(args)!=2:return True
        left,right=args
        if left.get('kind')=='constant' and right.get('kind')=='variable':
            left,right=right,left;name='below' if name=='above' else 'above'
        if left.get('kind')!='variable' or right.get('kind')!='constant':return True
        key=left['name'].lower();value=state.get(key,Value())
        if value.span is None:return True
        threshold=rational(right['value']);lo,hi=value.span
        if (name=='above')==truth:lo=max(lo,threshold)
        else:hi=min(hi,threshold)
        if lo>hi:return False
        state[key]=Value((lo,hi),value.real_defined,value.inputs)
        return True


def _literal_candidates(tree, assigned):
    """Source constants propose boxes; only induction gives them proof status."""
    literals={name:[] for name in assigned}
    def constants(node):
        if node.get('kind')=='constant':return [rational(node['value'])]
        return [v for child in node.get('args',[])+node.get('instructions',[]) for v in constants(child)]
    def visit(node):
        if node.get('function')=='assign':
            name=node['args'][0]['name'].lower()
            if name in literals:literals[name].extend(constants(node['args'][1]))
        for child in node.get('args',[])+node.get('instructions',[]):visit(child)
    if tree is not None:visit(tree)
    return literals


def shape_state_domain_evidence(source, *, policy, shape_index,
                                candidate_domains=None, initial_local_domains=None,
                                input_domains=None, initial_variable_policy=None):
    """Prove conditional nominal boxes for private state across all instances.

    Explicit candidates are obligations, never declarations. The native zero
    allocation policy requires the exact source34 engine; without it, private
    locals need explicit initializer assignments or caller-supplied init domains.
    Fresh reset/input variables and unbounded real state remain conditional finite
    premises. Results cannot amend native-domain or visible-motion evidence.
    """
    report={'policy':POLICY,'numeric_model':'nominal-real','status':'unresolved',
            'native_numeric_certified':False,'visible_motion_certified':False,
            'uses_equation_execution':False,'uses_shader_execution':False,'uses_rendered_images':False,
            'state_domains':{},'instance_output_domains':{},'obligations':{},'unknown_state_reasons':{},
            'unresolved_native_operations':[],'unresolved_native_finite_inputs':[],
            'source_identity':{'preset_sha256':source.get('preset_sha256'),'parser_inputs':source.get('parser_inputs')},
            'conditions':['Native intermediate finiteness, overflow, conversions and transcendental arithmetic remain unresolved',
                          'All source input/private-state values used in nominal arithmetic are real-valued premises',
                          'One complete instance transition is inductive; sequential instances do not reset private locals',
                          'State/output boxes do not prove visible movement, prominence or mood accuracy']}
    try:
        if type(shape_index) is not int or not 0<=shape_index<4:raise ValueError('shape index must be 0..3')
        if initial_variable_policy not in {None,ZERO_POLICY}:raise ValueError('unknown private-local initialization policy')
        if initial_variable_policy==ZERO_POLICY:
            from engine_profiles import CORE_2334_ENGINE, matches
            if not matches(source.get('parser_inputs',{}).get('engine',{}),CORE_2334_ENGINE):
                raise ValueError('native zero allocation requires exact source34 engine identity')
        sections=source.get('sections',{})
        # Shared register initialization/execution from any phase affects shapes.
        for prefix,section in sections.items():
            if prefix in {'warp_','comp_'}:continue
            selected=select_equation(section,prefix,policy=policy)
            if selected['compile_status'] not in {'accepted','omitted'}:
                raise ValueError('source equation compile status unresolved: '+prefix)
            if selected['compile_status']=='accepted' and selected['tree_status']!='parsed':
                raise ValueError('cross-phase source tree unresolved: '+prefix)
            def registers(node):
                if isinstance(node,dict):
                    if node.get('kind')=='variable' and re.fullmatch(r'reg[0-9]{2}',node['name'],re.I):return True
                    return any(registers(v) for v in node.values())
                return isinstance(node,list) and any(registers(v) for v in node)
            if registers(selected['tree']):raise ValueError('shared registers require cross-phase proof')
        trees=[];names=set();assigned=set()
        for suffix in ('init','per_frame'):
            prefix=f'shape_{shape_index}_{suffix}'
            selected=select_equation(sections.get(prefix),prefix,policy=policy)
            if selected['compile_status']=='omitted':tree=None
            elif selected['compile_status']!='accepted' or selected['tree_status']!='parsed':
                raise ValueError('accepted parsed shape source required: '+prefix)
            else:tree=selected['tree']
            n,a=_validate(tree);names|=n;assigned|=a;trees.append(tree)
        initial_tree,transition=trees
        _,transition_assigned=_validate(transition)
        private=names-RESET
        supplied=domains(initial_local_domains or {})
        declared=domains(input_domains or {})
        explicit=domains(candidate_domains or {}) if candidate_domains is not None else None
        if any(n not in private for n in supplied):raise ValueError('initial local domain must name private shape storage')
        if any(n not in RESET for n in declared):raise ValueError('input domain must name reset shape storage')
        if explicit is not None and any(n not in private for n in explicit):raise ValueError('candidate must name private shape storage')
        values=source_settings(source)
        defaults={n:Value((rational(v),rational(v))) for n,(default,kind) in SHAPE.items()
                  for v in [_scalar(values,f'shapecode_{shape_index}_{n}',default,kind)]}
        initial={n:Value(declared.get(n),True,frozenset({n})) for n in RESET}
        initial.update(defaults)
        initial.update({n:Value((Fraction(0),Fraction(0))) for n in T})
        initial['instance']=Value((Fraction(0),Fraction(0)))
        initial.update({n:Value(supplied.get(n,(Fraction(0),Fraction(0)) if initial_variable_policy==ZERO_POLICY else None)) for n in private})
        interpreter=Interpreter();interpreter.execute(initial_tree,initial)
        frame={n:Value(declared.get(n),True,frozenset({n})) for n in RESET}
        frame.update(defaults)
        frame.update({n:initial[n] for n in T})
        # Main-frame Q snapshots reload every instance, not shape-init Q writes.
        frame.update({n:Value(declared.get(n),True,frozenset({n})) for n in Q})
        def execute(boxes):
            state=dict(frame)
            state.update({n:Value(boxes.get(n),True,frozenset({n})) for n in private})
            return interpreter.execute(transition,state)
        literal=_literal_candidates(transition,private & transition_assigned)
        boxes={};reasons=report['unknown_state_reasons']
        for name in sorted(private):
            init=initial[name]
            if init.span is None or not init.real_defined:
                reasons[name]='initialization lacks a finite proved domain';continue
            if explicit is not None:
                if name not in explicit:continue
                box=explicit[name]
            else:
                endpoints=list(init.span)+literal.get(name,[])
                box=(min(endpoints),max(endpoints))
            if not (box[0]<=init.span[0]<=init.span[1]<=box[1]):
                reasons[name]='initialization is outside candidate box';continue
            boxes[name]=box
        # Bounded abstract enclosure search, not concrete frame propagation.
        # Inputs are arbitrary points in each proposed box on every query.
        for _ in range(8):
            output=execute(boxes);updated={}
            for name,box in boxes.items():
                new=output[name]
                if new.span is None or not new.real_defined:
                    reasons[name]='transition has unsupported/unbounded numerical dependency';continue
                joined=(min(box[0],new.span[0]),max(box[1],new.span[1]))
                if explicit is not None and joined!=box:
                    reasons[name]='transition leaves explicit candidate box';continue
                updated[name]=joined
            if updated==boxes:break
            boxes=updated
        # Final independent obligations retain only closed boxes. Repeat after
        # dropping failed boxes so a survivor cannot depend on a refuted premise.
        for _ in range(len(boxes)+1):
            output=execute(boxes);accepted={}
            for name,box in boxes.items():
                new=output[name]
                if (new.real_defined and new.span is not None and
                        box[0]<=new.span[0]<=new.span[1]<=box[1]):accepted[name]=box
                else:reasons[name]='one-instance transition is not inductively closed'
            if accepted==boxes:break
            boxes=accepted
        output=execute(boxes)
        report['state_domains']={n:export_span(span) for n,span in sorted(boxes.items())}
        report['obligations']={n:{'initialization':'proven','transition':'proven'} for n in sorted(boxes)}
        report['instance_output_domains']={n:export_span(output[n].span) for n in sorted(set(SHAPE)&transition_assigned)
            if output[n].span is not None and output[n].real_defined}
        report['unresolved_native_operations']=sorted(interpreter.unresolved_operations)
        report['unresolved_native_finite_inputs']=sorted(interpreter.finite_inputs)
        report['initial_variable_policy']=initial_variable_policy
        request={'initialization':initial_tree,'transition':transition,'candidate_domains':candidate_domains,
                 'initial_local_domains':initial_local_domains,'input_domains':input_domains,
                 'initial_variable_policy':initial_variable_policy,'equation_policy':policy,'shape_index':shape_index,
                 'native_shape_configuration':{n:export_span(v.span) for n,v in sorted(defaults.items())}}
        report['request_sha256']=hashlib.sha256(json.dumps(request,sort_keys=True,allow_nan=False).encode()).hexdigest()
        report['status']='proven' if boxes else 'unresolved'
    except (ValueError,KeyError,TypeError,RecursionError,OverflowError) as error:
        report.update(status='unsupported',reason=str(error))
    return report
