"""
Interacts


Examples
--------


Radio button example::

    @interact
    def f(n = Selector(values=["Option1","Option2"], selector_type="radio", label=" ")):
        print n


Push button example::

    result = 0
    @interact
    def f(n = Button(text="Increment", default=0, value=1, width="10em", label=" ")):
        global result
        result = result + n
        print "Result: ", result


Button bar example::

    result = 0
    @interact
    def f(n = ButtonBar(values=[(1,"Increment"),(-1,"Decrement")], default=0, width="10em", label=" ")):
        global result
        result = result + n
        print "Result: ", result

Multislider example::

    from interact_singlecell import *
    sliders = 5
    interval = [(0,10)]*sliders
    default = [3]*sliders
    @interact
    def f(n = MultiSlider(sliders = sliders, interval = interval, default = default), c = (1,100)):
        print "Sum of cn for all n: %s"%float(sum(c * i for i in n))

Nested interacts::

    from interact_singlecell import *
    @interact
    def f(n=(0,10)):
        print n
        @interact
        def transformation(c=(0,n)):
            print c


Nested interacts where the number of controls is changed::

    from interact_singlecell import *
    @interact
    def f(n=(0,10)):
        @interact(controls=[('x%d'%i, (0,10)) for i in range(n)])
        def s(multiplier=2, **kwargs):
            print sum(kwargs.items())*multiplier


Recursively nested interact::


    from interact_singlecell import *
    c=1
    @interact
    def f(n=(0,10)):
        global c
        c+=1
        print 'f evaluated %d times'%c
        for i in range(n):
            interact(f)


"""

import singlecell_exec_config as CONFIG

_INTERACTS={}

__single_cell_timeout__=0

from functools import wraps

def decorator_defaults(func):
    """
    This function allows a decorator to have default arguments.

    Normally, a decorator can be called with or without arguments.
    However, the two cases call for different types of return values.
    If a decorator is called with no parentheses, it should be run
    directly on the function.  However, if a decorator is called with
    parentheses (i.e., arguments), then it should return a function
    that is then in turn called with the defined function as an
    argument.

    This decorator allows us to have these default arguments without
    worrying about the return type.

    EXAMPLES::
    
        sage: from sage.misc.decorators import decorator_defaults
        sage: @decorator_defaults
        ... def my_decorator(f,*args,**kwds):
        ...     print kwds
        ...     print args
        ...     print f.__name__
        ...       
        sage: @my_decorator
        ... def my_fun(a,b):
        ...     return a,b
        ...  
        {}
        ()
        my_fun
        sage: @my_decorator(3,4,c=1,d=2)
        ... def my_fun(a,b):
        ...     return a,b
        ...   
        {'c': 1, 'd': 2}
        (3, 4)
        my_fun
    """
    from inspect import isfunction
    @wraps(func)
    def my_wrap(*args,**kwargs):
        if len(kwargs)==0 and len(args)==1 and isfunction(args[0]):
            # call without parentheses
            return func(*args)
        else:
            def _(f):
                return func(f, *args, **kwargs)
            return _
    return my_wrap

@decorator_defaults
def interact(f, controls=[]):
    """
    A decorator that creates an interact.

    Each control can be given as an :class:`.InteractControl` object
    or a value, defined in :func:`.automatic_control`, that will be
    interpreted as the parameters for some control.

    The decorator can be used in several ways::

        @interact([name1, (name2, control2), (name3, control3)])
        def f(**kwargs):
            ...

        @interact
        def f(name1, name2=control2, name3=control3):
            ...


    The two ways can also be combined::

        @interact([name1, (name2, control2)])
        def f(name3, name4=control4, name5=control5):
            ...

    In each example, ``name1``, with no associated control,
    will default to a text box.

    :arg function f: the function to make into an interact
    :arg list controls: a list of tuples of the form ``("name",control)``
    :returns: the original function
    :rtype: function
    """
    global _INTERACTS

    if isinstance(controls,(list,tuple)):
        controls=list(controls)
        for i,name in enumerate(controls):
            if isinstance(name, str):
                controls[i]=(name, None)
            elif not isinstance(name[0], str):
                raise ValueError("interact control must have a string name, but %s isn't a string"%(name[0],))

    import inspect
    (args, varargs, varkw, defaults) = inspect.getargspec(f)
    if defaults is None:
        defaults=[]
    n=len(args)-len(defaults)
    
    controls=zip(args,[None]*n+list(defaults))+controls

    names=[n for n,_ in controls]
    controls=[automatic_control(c) for _,c in controls]

    from sys import _sage_messages as MESSAGE, maxint
    from random import randrange

    # UUID would be better, but we can't use it because of a
    # bug in Python 2.6 on Mac OS X (http://bugs.python.org/issue8621)
    function_id=str(randrange(maxint))

    def adapted_f(**kwargs):
        MESSAGE.push_output_id(function_id)
        # remap parameters
        for k,v in kwargs.items():
            kwargs[k]=controls[names.index(k)].adapter(v)
        returned=f(**kwargs)
        MESSAGE.pop_output_id()
        return returned

    _INTERACTS[function_id]=adapted_f
    MESSAGE.message_queue.message('interact_prepare',
                                  {'interact_id':function_id,
                                   'controls':dict(zip(names,[c.message() for c in controls])),
                                   'layout':names})
    global __single_cell_timeout__
    __single_cell_timeout__=60
    adapted_f(**dict(zip(names,[c.default for c in controls])))
    return f

class InteractControl:
    """
    Base class for all interact controls.
    """
    def __init__(self, *args, **kwargs):
        self.args=args
        self.kwargs=kwargs

    def adapter(self, v):
        """
        Get the value of the interact in a form that can be passed to
        the inner function

        :arg v: a value as passed from the client
        :returns: the interpretation of that value in the context of
            this control (by default, the value is not changed)
        """
        return v

    def message(self):
        """
        Get a control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        raise NotImplementedError

class Checkbox(InteractControl):
    """
    A checkbox control

    :arg bool default: ``True`` if the checkbox is checked by default
    :arg bool raw: ``True`` if the value should be treated as "unquoted"
        (raw), so it can be used in control structures. There are few
        conceivable situations in which raw should be set to ``False``,
        but it is available.
    :arg str label: the label of the control
    """
    def __init__(self, default=True, raw=True, label=""):
        self.default=default
        self.raw=raw
        self.label=label

    def message(self):
        """
        Get a checkbox control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type':'checkbox',
                'default':self.default,
                'raw':self.raw,
                'label':self.label}

class InputBox(InteractControl):
    """
    An input box control

    :arg default: default value of the input box
    :arg int width: character width of the input box
    :arg bool raw: ``True`` if the value should be treated as "unquoted"
        (raw), so it can be used in control structures; ``False`` if the
        value should be treated as a string
    :arg str label: the label of the control
    """

    def __init__(self, default="", width=0, raw=False, label=""):
        self.default=self.default_return=default
        self.width=int(width)
        self.raw=raw
        self.label=label
    
        if self.raw:
            self.default_return = repr(self.default)

    def message(self):
        """
        Get an input box control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type':'input_box',
                'default':self.default_return,
                'width':self.width,
                'raw':self.raw,
                'label':self.label}

class InputGrid(InteractControl):
    """
    An input grid control

    :arg int nrows: number of rows in the grid
    :arg int ncols: number of columns in the grid
    :arg int width: character width of each input box
    :arg default: default values of the control. A multi-dimensional
        list specifies the values of individual inputs; a single value
        sets the same value to all inputs
    :arg bool raw: ``True`` if the value should be treated as "unquoted"
        (raw), so it can be used in control structures; ``False`` if the
        value should be treated as a string
    :arg str label: the label of the control
    """

    def __init__(self, nrows=1, ncols=1, width=0, default=0, raw=True, label=""):
        self.nrows = int(nrows)
        self.ncols = int(ncols)
        self.width = int(width)
        self.raw = raw
        self.label = label

        if not isinstance(default, list):
            self.default = self.default_return = [[default for _ in range(self.ncols)] for _ in range(self.nrows)]
        else:
            self.default = self.default_return = default

        if self.raw:
            self.default_return = [[repr(j) for j in i] for i in self.default]

    def message(self):
        """
        Get an input box control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type': 'input_grid',
                'nrows': self.nrows,
                'ncols': self.ncols,
                'default': self.default_return,
                'width':self.width,
                'raw': self.raw,
                'label': self.label}

class Selector(InteractControl):
    """
    A selector interact control

    :arg int default: initially selected index of the list of values
    :arg list values: list of values from which the user can select. A value can
        also be represented as a tuple of the form ``(value, label)``, where the
        value is the name of the variable and the label is the text displayed to
        the user.
    :arg string selector_type: Type of selector. Currently supported options
        are "button" (Buttons), "radio" (Radio buttons), and "list"
        (Dropdown list), with "list" being the default. If "list" is used,
        ``ncols`` and ``nrows`` will be ignored. If "radio" is used, ``width``
        will be ignored.
    :arg int ncols: number of columns of selectable objects. If this is given,
        it must cleanly divide the number of objects, else this value will be
        set to the number of objects and ``nrows`` will be set to 1.
    :arg int nrows: number of rows of selectable objects. If this is given, it
        must cleanly divide the number of objects, else this value will be set
        to 1 and ``ncols`` will be set to the number of objects. If both
        ``ncols`` and ``nrows`` are given, ``nrows * ncols`` must equal the
        number of objects, else ``nrows`` will be set to 1 and ``ncols`` will
        be set to the number of objects.
    :arg string width: CSS width of each button. This should be specified in
        px or em.
    :arg str label: the label of the control
    """

    def __init__(self, default=0, values=[0], selector_type="list", nrows=None, ncols=None, width="", label=""):
        self.default=int(default)
        self.values=values[:]
        self.selector_type=selector_type
        self.nrows=nrows
        self.ncols=ncols
        self.width=str(width)
        self.label=label

        if self.selector_type != "button" and self.selector_type != "radio":
            self.selector_type = "list"
        
        # Assign selector labels and values.
        self.value_labels=[str(v[1]) if isinstance(v,tuple) and
                           len(v)==2 else str(v) for v in values]
        self.values = [v[0] if isinstance(v,tuple) and
                       len(v)==2 else v for v in values]

        # Ensure that default index is always in the correct range.
        if default < 0 or default >= len(values):
            self.default = 0

        # If not using a dropdown list,
        # check/set rows and columns for layout.
        if self.selector_type != "list":
            if self.nrows is None and self.ncols is None:
                self.nrows = 1
                self.ncols = len(self.values)
            elif self.nrows is None:
                self.ncols = int(self.ncols)
                if self.ncols <= 0:
                    self.ncols = len(values)
                self.nrows = int(len(self.values) / self.ncols)
                if self.ncols * self.nrows < len(self.values):
                    self.nrows = 1
                    self.ncols = len(self.values)
            elif self.ncols is None:
                self.nrows = int(self.nrows)
                if self.nrows <= 0:
                    self.nrows = 1
                self.ncols = int(len(self.values) / self.nrows)
                if self.ncols * self.nrows < len(self.values):
                    self.nrows = 1
                    self.ncols = len(self.values)
            else:
                self.ncols = int(self.ncols)
                self.nrows = int(self.nrows)
                if self.ncols * self.nrows != len(self.values):
                    self.nrows = 1
                    self.ncols = len(self.values)

    def message(self):
        """
        Get a selector control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type': 'selector',
                'subtype': self.selector_type,
                'values': range(len(self.values)),
                'value_labels': self.value_labels,
                'default': self.default,
                'nrows': self.nrows,
                'ncols': self.ncols,
                'raw': True,
                'width': self.width,
                'label':self.label}
                
    def adapter(self, v):
        return self.values[int(v)]

class DiscreteSlider(InteractControl):
    """
    A discrete slider interact control.

    The slider value correlates with the index of an array of values.

    :arg int default: initial value (index) of the slider; if ``None``, the
        slider defaults to the 0th index.  The default will be the
        closest values to this parameter.
    :arg list values: list of values to which the slider position refers.
    :arg bool range_slider: toggles whether the slider should select
        one value (False, default) or a range of values (True).
    :arg str label: the label of the control
    """

    def __init__(self, range_slider=False, values=[0,1], default=None, label=""):
        from types import GeneratorType

        if isinstance(values, GeneratorType):
            self.values = take(10000, values)
        else:
            self.values = values[:]

        if len(self.values) < 2:
            self.values = [0,1]

        self.range_slider = range_slider
        
        # self.default is an *index* or tuple of indices.
        if self.range_slider:
            self.subtype = "discrete_range"
            if default is None:
                self.default = (0,len(values))
            elif not isinstance(default, tuple) or len(default)!=2:
                raise TypeError("default value must be None or a 2-tuple.")
            else:
                self.default=tuple(_old_determine_default_index(values,
                                                                 d)
                                   for d in default)
        else:
            self.subtype = "discrete"
            self.default = _old_determine_default_index(self.values,
                                                        default)

        self.label=label

    def message(self):
        """
        Get a discrete slider control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type':'slider',
                'subtype':self.subtype,
                'default':self.default,
                'range':[0, len(self.values)-1],
                'values':[repr(i) for i in self.values],
                'step':1,
                'raw':True,
                'label':self.label}
    def adapter(self,v):
        if self.range_slider:
            return [self.values[int(i)] for i in v]
        else:
            return self.values[int(v)]

class ContinuousSlider(InteractControl):
    """
    A continuous slider interact control.

    The slider value moves between a range of numbers.

    :arg int default: initial value (index) of the slider; if ``None``, the
        slider defaults to its minimum
    :arg tuple interval: range of the slider, in the form ``(min, max)``
    :arg int steps: number of steps the slider should have between min and max
    :arg Number stepsize: size of step for the slider. If both step and stepsized are specified, stepsize takes precedence so long as it is valid.
    :arg bool range_slider: toggles whether the slider should select one value (default = False) or a range of values (True).
    :arg str label: the label of the control
    
    Note that while "number of steps" and/or "stepsize" can be specified for the slider, this is to enable snapping, rather than a restriction on the slider's values. The only restrictions placed on the values of the slider are the endpoints of its range.
    """

    def __init__(self, range_slider=False, interval=(0,100), default=None, steps=250, stepsize=0, label=""):
        self.range_slider = range_slider
        self.interval = interval if interval[0] < interval[1] and len(interval) == 2 else (0,100)
        
        if self.range_slider:
            self.subtype = "continuous_range"
            self.default = default if default is not None and len(default) == 2 else [self.interval[0], self.interval[1]]
            for i in range(2):
                if not (self.default[i] > self.interval[0] and self.default[i] < self.interval[1]):
                    self.default[i] = self.interval[i]
            self.default_return = [float(i) for i in self.default]
        else:
            self.subtype = "continuous"
            self.default = default if default is not None and default < self.interval[1] and default > self.interval[0] else self.interval[0]
            self.default_return = float(self.default)

        self.steps = int(steps) if steps > 0 else 250
        self.stepsize = float(stepsize if stepsize > 0 and stepsize <= self.interval[1] - self.interval[0] else float(self.interval[1] - self.interval[0]) / self.steps)
        self.label = label

    def message(self):
        """
        Get a continuous slider control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type':'slider',
                'subtype':self.subtype,
                'default':self.default_return,
                'range':[float(i) for i in self.interval],
                'step':self.stepsize,
                'raw':True,
                'label':self.label}

class MultiSlider(InteractControl):
    """
    A multiple-slider interact control.

    Defines a bank of vertical sliders (either discrete or continuous sliders, but not both in the same control).

    :arg string slider_type: type of sliders to generate. Currently, only "continuous" and "discrete" are valid, and other input defaults to "continuous."
    :arg int sliders: Number of sliders to generate
    :arg list default: Default value (continuous sliders) or index position (continuous sliders) of each slider. The length of the list should be equivalent to the number of sliders, but if all sliders are to have the same default value, the list only needs to contain that one value.
    :arg list values: Values for each value slider in a multi-dimensional list for the form [[slider_1_val_1..slider_1_val_n], ... ,[slider_n_val_1, .. ,slider_n_val_n]]. The length of the first dimension of the list should be equivalent to the number of sliders, but if all sliders are to iterate through the same values, the list only needs to contain that one list of values.
    :arg list interval: Intervals for each continuous slider in a list of tuples of the form [(min_1, max_1), ... ,(min_n, max_n)]. This parameter cannot be set if value sliders are specified. The length of the first dimension of the list should be equivalent to the number of sliders, but if all sliders are to have the same interval, the list only needs to contain that one tuple.
    :arg list stepsize: List of numbers representing the stepsize for each continuous slider. The length of the list should be equivalent to the number of sliders, but if all sliders are to have the same stepsize, the list only needs to contain that one value.
    :arg list steps: List of numbers representing the number of steps for each continuous slider. Note that (as in the case of the regular continuous slider), specifying a valid stepsize will always take precedence over any specification of number of steps, valid or not. The length of this list should be equivalent to the number of sliders, but if all sliders are to have the same number of steps, the list only neesd to contain that one value.
    :arg str label: the label of the control
    """

    def __init__(self, slider_type="continuous", sliders=1, default=[0], interval=[(0,1)], values=[[0,1]], stepsize=[0], steps=[250], label=""):
        from types import GeneratorType

        self.slider_type = slider_type

        self.sliders = int(sliders) if sliders > 0 else 1
        self.slider_range = range(self.sliders)
        
        if self.slider_type == "discrete":
            self.stepsize = 1

            if len(values) == self.sliders:
                self.values = values[:]
            elif len(values) == 1 and len(values[0]) >= 2:
                self.values = [values[0]] * self.sliders
            else:
                self.values = [[0,1]] * self.sliders

            self.values = [i if not isinstance(i, GeneratorType) else take(10000, i) for i in self.values]

            self.interval = [(0, len(self.values[i])-1) for i in self.slider_range]

            if len(default) == self.sliders:
                self.default = [default[i] if i >= self.interval[i][0] and i <= self.interval[i][1] else 0 for i in default]
            elif len(default) == 1:
                self.default = [default[0] if default[0] >= self.interval[i][0] and i <= self.interval[i][1] else 0 for i in self.slider_range]
            else:
                self.default = [0] * self.sliders

        else:
            self.slider_type = "continuous"

            if len(interval) == self.sliders:
                self.interval = interval[:]
            elif len(interval) == 1 and len(interval[0]) == 2:
                self.interval = [interval[0]] * self.sliders
            else:
                self.interval = [(0,1) for i in self.slider_range]

            for i in self.slider_range:
                if not len(self.interval[i]) == 2 or self.interval[i][0] > self.interval[i]:
                    self.interval[i] = (0,1)
                else:
                    self.interval[i] = [float(j) for j in self.interval[i]]

            if len(default) == self.sliders:
                self.default = [default[i] if default[i] > self.interval[i][0] and default[i] < self.interval[i][1] else self.interval[i][0] for i in self.slider_range]
            elif len(default) == 1:
                self.default = [default[0] if default[0] > self.interval[i][0] and default[0] < self.interval[i][1] else self.interval[i][0] for i in self.slider_range]
            else:
                self.default = [self.interval[i][0] for i in self.slider_range]

            self.default_return = [float(i) for i in self.default]

            if len(steps) == 1:
                self.steps = [steps[0]] * self.sliders if steps[0] > 0 else [250] * self.sliders
            else:
                self.steps = [int(i) if i > 0 else 250 for i in steps] if len(steps) == self.sliders else [250 for i in self.slider_range]

            if len(stepsize) == self.sliders:
                self.stepsize = [float(stepsize[i]) if stepsize[i] > 0 and stepsize[i] <= self.interval[i][1] - self.interval[i][0] else float(self.interval[i][1] - self.interval[i][0]) / self.steps[i] for i in self.slider_range]
            elif len(stepsize) == 1:
                self.stepsize = [float(stepsize[0]) if stepsize[0] > 0 and stepsize[0] <= self.interval[i][1] - self.interval[i][0] else float(self.interval[i][1] - self.interval[i][0]) / self.steps[i] for i in self.slider_range]
            else:
                self.stepsize = [float(self.interval[i][1] - self.interval[i][0]) / self.steps[i] for i in self.slider_range]

        self.label = label

    def message(self):
        """
        Get a multi_slider control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return_message = {'control_type':'multi_slider',
                          'subtype':self.slider_type,
                          'sliders':self.sliders,
                          'label':self.label,
                          'range':self.interval,
                          'step':self.stepsize,
                          'raw':True,
                          'label':self.label}
        if self.slider_type == "discrete":
            return_message["values"] = [[repr(j) for j in self.values[i]] for i in self.slider_range]
            return_message["default"] = self.default
        else:
            return_message["default"] = self.default_return
        return return_message

    def adapter(self,v):
        if self.slider_type == "discrete":
            return [self.values[i][v[i]] for i in self.slider_range]
        else:
            return v

class ColorSelector(InteractControl):
    """
    A color selector interact control

    :arg default: initial color (either as an html hex string or a Sage Color object, if sage is installed.
    :arg bool sage_color: Toggles whether the return value should be a Sage Color object (True) or html hex string (False). If Sage is unavailable or if the user has deselected "sage mode" for the computation, this value will always end up False, regardless of whether the user specified otherwise in the interact.
    :arg str label: the label of the control
    """

    def __init__(self, default="#000000", sage_color=True, label=""):
        self.sage_color = sage_color

        self.sage_mode = CONFIG.EMBEDDED_MODE["sage_mode"]
        self.enable_sage = CONFIG.EMBEDDED_MODE["enable_sage"]

        if self.sage_mode and self.enable_sage and self.sage_color:
            from sagenb.misc.misc import Color
            if isinstance(default, Color):
                self.default = default
            elif isinstance(default, str):
                self.default = Color(default)
            else:
                Color("#000000")
        else:
            self.default = default if isinstance(default,str) else "#000000"

        self.label = label

    def message(self):
        """
        Get a color selector control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        self.return_value =  {'control_type':'color_selector',
                         'raw':False,
                         'label':self.label}

        if self.sage_mode and self.enable_sage and self.sage_color:
            self.return_value["default"] = self.default.html_color()
        else:
            self.return_value["default"] = self.default
        return self.return_value

    def adapter(self, v):
        if self.sage_mode and self.enable_sage and self.sage_color:
            from sagenb.misc.misc import Color
            return Color(v)
        else:
            return v

class Button(InteractControl):
    """
    A button interact control
    
    :arg string text: button text
    :arg value: value of the button, when pressed.
    :arg default: default value that should be used if the button is not
        pushed. This **must** be specified.
    :arg string width: CSS width of the button. This should be specified in
        px or em.
    :arg str label: the label of the control
    """
    def __init__(self, text="Button", value = "", default="", width="", label=""):
        self.text = text
        self.width = width
        self.value = value
        self.default = False
        self.default_value = default
        self.label = label

    def message(self):
        return {'control_type':'button',
                'width':self.width,
                'text':self.text,
                'raw': True,
                'label': self.label}

    def adapter(self, v):
        if v:
            return self.value
        else:
            return self.default_value

class ButtonBar(InteractControl):
    """
    A button bar interact control
    
    :arg list values: list of values from which the user can select. A value can
        also be represented as a tuple of the form ``(value, label)``, where the
        value is the name of the variable and the label is the text displayed to
        the user.
    :arg default: default value that should be used if no button is pushed.
        This **must** be specified.
    :arg int ncols: number of columns of selectable buttons. If this is given,
        it must cleanly divide the number of buttons, else this value will be
        set to the number of buttons and ``nrows`` will be set to 1.
    :arg int nrows: number of rows of buttons. If this is given, it must cleanly
        divide the total number of objects, else this value will be set to 1 and
        ``ncols`` will be set to the number of buttosn. If both ``ncols`` and
        ``nrows`` are given, ``nrows * ncols`` must equal the number of buttons,
        else ``nrows`` will be set to 1 and ``ncols`` will be set to the number
        of objects.
    :arg string width: CSS width of each button. This should be specified in
        px or em.
    :arg str label: the label of the control
    """
    def __init__(self, values=[0], default="", nrows=None, ncols=None, width="", label=""):
        self.default = None
        self.default_value = default
        self.values = values[:]
        self.nrows = nrows
        self.ncols = ncols
        self.width = str(width)
        self.label = label

        # Assign button labels and values.
        self.value_labels=[str(v[1]) if isinstance(v,tuple) and
                           len(v)==2 else str(v) for v in values]
        self.values = [v[0] if isinstance(v,tuple) and
                       len(v)==2 else v for v in values]

        # Check/set rows and columns for layout
        if self.nrows is None and self.ncols is None:
            self.nrows = 1
            self.ncols = len(self.values)
        elif self.nrows is None:
            self.ncols = int(self.ncols)
            if self.ncols <= 0:
                self.ncols = len(values)
            self.nrows = int(len(self.values) / self.ncols)
            if self.ncols * self.nrows < len(self.values):
                self.nrows = 1
                self.ncols = len(self.values)
        elif self.ncols is None:
            self.nrows = int(self.nrows)
            if self.nrows <= 0:
                self.nrows = 1
            self.ncols = int(len(self.values) / self.nrows)
            if self.ncols * self.nrows < len(self.values):
                self.nrows = 1
                self.ncols = len(self.values)
        else:
            self.ncols = int(self.ncols)
            self.nrows = int(self.nrows)
            if self.ncols * self.nrows != len(self.values):
                self.nrows = 1
                self.ncols = len(self.values)

    def message(self):
        """
        Get a button bar control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type': 'button_bar',
                'values': range(len(self.values)),
                'value_labels': self.value_labels,
                'nrows': self.nrows,
                'ncols': self.ncols,
                'raw': True,
                'width': self.width,
                'label': self.label}

    def adapter(self,v):
        if v is None:
            return self.default_value
        else:
            return self.values[int(v)]

def automatic_control(control):
    """
    Guesses the desired interact control from the syntax of the parameter.
    
    :arg control: Parameter value.
    
    :returns: An InteractControl object.
    :rtype: InteractControl
    
    
    """
    from numbers import Number
    from types import GeneratorType
    label = ""
    default_value = 0
    
    # Checks for interact controls that are verbosely defined
    if isinstance(control, InteractControl):
        return control
    
    # Checks for labels and control values
    for _ in range(2):
        if isinstance(control, tuple) and len(control) == 2 and isinstance(control[0], str):
            label, control = control
        if isinstance(control, tuple) and len(control) == 2 and isinstance(control[1], (tuple, list, GeneratorType)):
            default_value, control = control

    if isinstance(control, str):
        C = input_box(default = control, label = label)
    elif isinstance(control, bool):
        C = checkbox(default = control, label = label, raw = True)
    elif isinstance(control, Number):
        C = input_box(default = control, label = label, raw = True)
    elif isinstance(control, list):
        C = selector(buttons = len(control) <= 5, default = default_value, label = label, values = control, raw = False)
    elif isinstance(control, GeneratorType):
        C = discrete_slider(default = default_value, values = take(10000,control), label = label)
    elif isinstance (control, tuple):
        if len(control) == 2:
            C = continuous_slider(default = default_value, interval = (control[0], control[1]), label = label)
        elif len(control) == 3:
            C = continuous_slider(default = default_value, interval = (control[0], control[1]), stepsize = control[2], label = label)
        else:
            C = discrete_slider(default = default_value, values = list(control), label = label)
    else:
        C = input_box(default = control, label=label, raw = True)

        if CONFIG.EMBEDDED_MODE["sage_mode"] and CONFIG.EMBEDDED_MODE["enable_sage"]:
            from sagenb.misc.misc import is_Matrix, Color
            if is_Matrix(control):
                default_value = control.list()
                nrows = control.nrows()
                ncols = control.ncols()
                default_value = [[default_value[j * ncols + i] for i in range(ncols)] for j in range(nrows)]
                C = input_grid(nrows = nrows, ncols = ncols, label = label, default = default_value)
            elif isinstance(control, Color):
                C = color_selector(default = control, label = label)
    
    return C

def take(n, iterable):
    """
    Return the first n elements of an iterator as a list.

    :arg int n: Number of elements through which v should be iterated.
    :arg iterable: An iterator.

    :returns: First n elements of iterable.
    :rtype: List
    """

    from itertools import islice
    return list(islice(iterable, n))

#############################################################################
# Aliases for backwards compatibility
#############################################################################

import math
def __old_make_values_list(vmin, vmax, step_size):
    """
    This code is from slider_generic.__init__.

    This code requires sage mode to be checked.
    """
    from sagenb.misc.misc import srange
    if isinstance(vmin, list):
        vals=vmin
    else:
        if vmax is None:
            vmax=vmin
            vmin=0
        #Compute step size; vmin and vmax are both defined here
        #500 is the length of the slider (in px)
        if step_size is None:
            step_size = (vmax-vmin)/499.0
        elif step_size <= 0:
            raise ValueError, "invalid negative step size -- step size must be positive"

        #Compute list of values
        num_steps = int(math.ceil((vmax-vmin)/float(step_size)))
        if num_steps <= 2:
            vals = [vmin, vmax]
        else:
            vals = srange(vmin, vmax, step_size, include_endpoint=True)
            if vals[-1] != vmax:
                try:
                    if vals[-1] > vmax:
                        vals[-1] = vmax
                    else:
                        vals.append(vmax)
                except (ValueError, TypeError):
                    pass
                
        #Is the list of values is small (len<=50), use the whole list.
        #Otherwise, use part of the list.
        if len(vals) == 0:
            return_values = [0]   
        elif(len(vals)<=500):
            return_values = vals
        else:
            vlen = (len(vals)-1)/499.0
            return_values = [vals[(int)(i*vlen)] for i in range(500)]

        return return_values

def _old_determine_default_index(values, default):
    """
    From sage notebook's interact.py file
    """
    # determine the best choice of index into the list of values
    # for the user-selected default. 
    if default is None:
        index = 0
    else:
        try:
            i = values.index(default)
        except ValueError:
            # here no index matches -- which is best?
            try:
                v = [(abs(default - values[j]), j) for j in range(len(values))]
                m = min(v)
                i = m[1]
            except TypeError: # abs not defined on everything, so give up
                i = 0
        index = i
    return index


def slider(vmin, vmax=None,step_size=None, default=None, label=None,
           display_value=True):
    r"""
    An interactive slider control, which can be used in conjunction
    with the :func:`interact` command.

    INPUT:

    - ``vmin`` - an object

    - ``vmax`` - an object (default: None); if None then ``vmin``
      must be a list, and the slider then varies over elements of
      the list.

    - ``step_size`` - an integer (default: 1)

    - ``default`` - an object (default: None); default value is
      "closest" in ``vmin`` or range to this default.

    - ``label`` - a string

    - ``display_value`` - a bool, whether to display the current
      value to the right of the slider

    EXAMPLES:

    We specify both ``vmin`` and ``vmax``.  We make the default
    `3`, but since `3` isn't one of `3/17`-th spaced values
    between `2` and `5`, `52/17` is instead chosen as the
    default (it is closest)::

        sage: slider(2, 5, 3/17, 3, 'alpha')
        Slider: alpha [2--|52/17|---5]

    Here we give a list::

        sage: slider([1..10], None, None, 3, 'alpha')
        Slider: alpha [1--|3|---10]

    The elements of the list can be anything::

        sage: slider([1, 'x', 'abc', 2/3], None, None, 'x', 'alpha')
        Slider: alpha [1--|x|---2/3]            
        """        r"""
    An interactive slider control, which can be used in conjunction
    with the :func:`interact` command.

    INPUT:

    - ``vmin`` - an object

    - ``vmax`` - an object (default: None); if None then ``vmin``
      must be a list, and the slider then varies over elements of
      the list.

    - ``step_size`` - an integer (default: 1)

    - ``default`` - an object (default: None); default value is
      "closest" in ``vmin`` or range to this default.

    - ``label`` - a string

    - ``display_value`` - a bool, whether to display the current
      value to the right of the slider

    EXAMPLES:

    We specify both ``vmin`` and ``vmax``.  We make the default
    `3`, but since `3` isn't one of `3/17`-th spaced values
    between `2` and `5`, `52/17` is instead chosen as the
    default (it is closest)::

        sage: slider(2, 5, 3/17, 3, 'alpha')
        Slider: alpha [2--|52/17|---5]

    Here we give a list::

        sage: slider([1..10], None, None, 3, 'alpha')
        Slider: alpha [1--|3|---10]

    The elements of the list can be anything::

        sage: slider([1, 'x', 'abc', 2/3], None, None, 'x', 'alpha')
        Slider: alpha [1--|x|---2/3]            
    """
    values=__old_make_values_list(vmin, vmax, step_size)
    if label is None:
        label = ""
    return DiscreteSlider(range_slider=False, values=values, 
                          default=default, label=label)


def range_slider(vmin, vmax=None, step_size=None, default=None, label=None, display_value=True):
    r"""
    An interactive range slider control, which can be used in conjunction
    with the :func:`interact` command.

    INPUT:

    - ``vmin`` - an object

    - ``vmax`` - object or None; if None then ``vmin`` must be a
      list, and the slider then varies over elements of the list.

    - ``step_size`` - integer (default: 1)

    - ``default`` - a 2-tuple of objects (default: None); default
      range is "closest" in ``vmin`` or range to this default.

    - ``label`` - a string

    - ``display_value`` - a bool, whether to display the current
      value below the slider

    EXAMPLES:

    We specify both ``vmin`` and ``vmax``.  We make the default
    `(3,4)` but since neither is one of `3/17`-th spaced
    values between `2` and `5`, the closest values: `52/17`
    and `67/17`, are instead chosen as the default::

        sage: range_slider(2, 5, 3/17, (3,4), 'alpha')
        Range Slider: alpha [2--|52/17==67/17|---5]

    Here we give a list::

        sage: range_slider([1..10], None, None, (3,7), 'alpha')
        Range Slider: alpha [1--|3==7|---10]
    """
    values=__old_make_values_list(vmin, vmax, step_size)
    if label is None:
        label = ""
    return DiscreteSlider(range_slider=True, values=values, 
                          default=default, label=label)


def input_box(default=None, label=None, type=None, width=80, height=1, **kwargs):
    r"""
    An input box interactive control.  Use this in conjunction
    with the :func:`interact` command.

    INPUT:

    - ``default`` - an object; the default put in this input box

    - ``label`` - a string; the label rendered to the left of the
      box.

    - ``type`` - a type; coerce inputs to this; this doesn't
      have to be an actual type, since anything callable will do.

    - ``height`` - an integer (default: 1); the number of rows.  
      If greater than 1 a value won't be returned until something
      outside the textarea is clicked.

    - ``width`` - an integer; width of text box in characters

    - ``kwargs`` - a dictionary; additional keyword options

    EXAMPLES::

        sage: input_box("2+2", 'expression')
        Interact input box labeled 'expression' with default value '2+2'
        sage: input_box('sage', label="Enter your name", type=str)
        Interact input box labeled 'Enter your name' with default value 'sage'   
        sage: input_box('Multiline\nInput',label='Click to change value',type=str,height=5)
        Interact input box labeled 'Click to change value' with default value 'Multiline\nInput'
    """
    if label is None:
        label = ""

    # TODO: make input_box take a height and type
    if type is Color:
        # kwargs are only used if the type is Color.  
        widget=kwargs.get('widget', None)
        hide_box=kwargs.get('hide_box', False)
        return color_selector(default=default, label=label, 
                              widget=widget, hide_box=hide_box)
    
    return InputBox(default=default, width=width, 
                    label=label, value_type=type, height=height)

def color_selector(default=(0,0,1), label=None,
                 widget='colorpicker', hide_box=False):
    r"""
    A color selector (also called a color chooser, picker, or
    tool) interactive control.  Use this with the :func:`interact`
    command.

    INPUT:

    - ``default`` - an instance of or valid constructor argument
      to :class:`Color` (default: (0,0,1)); the selector's default
      color; a string argument must be a valid color name (e.g.,
      'red') or HTML hex color (e.g., '#abcdef')

    - ``label`` - a string (default: None); the label rendered to
      the left of the selector.

    - ``widget`` - a string (default: 'jpicker'); the color
      selector widget to use; choices are 'colorpicker', 'jpicker'
      and 'farbtastic'

    - ``hide_box`` - a boolean (default: False); whether to hide
      the input box associated with the color selector widget

    EXAMPLES::

        sage: color_selector()
        Interact color selector labeled None, with default RGB color (0.0, 0.0, 1.0), widget 'jpicker', and visible input box
        sage: color_selector((0.5, 0.5, 1.0), widget='jpicker')
        Interact color selector labeled None, with default RGB color (0.5, 0.5, 1.0), widget 'jpicker', and visible input box
        sage: color_selector(default = Color(0, 0.5, 0.25))
        Interact color selector labeled None, with default RGB color (0.0, 0.5, 0.25), widget 'jpicker', and visible input box
        sage: color_selector('purple', widget = 'colorpicker')
        Interact color selector labeled None, with default RGB color (0.50..., 0.0, 0.50...), widget 'colorpicker', and visible input box
        sage: color_selector('crayon', widget = 'colorpicker')
        Traceback (most recent call last):
        ...
        ValueError: unknown color 'crayon'
        sage: color_selector('#abcdef', label='height', widget='jpicker')
        Interact color selector labeled 'height', with default RGB color (0.6..., 0.8..., 0.9...), widget 'jpicker', and visible input box
        sage: color_selector('abcdef', label='height', widget='jpicker')
        Traceback (most recent call last):
        ...
        ValueError: unknown color 'abcdef'
    """
    # TODO: look at various other widgets we used to support
        #'widget': 'jpicker, 'colorpicker', 'farbtastic' 
        #    -- we don't need to support each one right now
    if label is None:
        label=""
    if widget!='colorpicker':
        print "ColorSelector: Only widget='colorpicker' is supported; changing color widget"
    # TODO: make 'hide_box': True/False (whether to hide the input box for the color widget)
    return ColorSelector(default=default, label=label)

def selector(values, label=None, default=None,
                 nrows=None, ncols=None, width=None, buttons=False):
    r"""
    A drop down menu or a button bar that when pressed sets a
    variable to a given value.  Use this in conjunction with the
    :func:`interact` command.

    We use the same command to create either a drop down menu or
    selector bar of buttons, since conceptually the two controls
    do exactly the same thing - they only look different.  If
    either ``nrows`` or ``ncols`` is given, then you get a buttons
    instead of a drop down menu.

    INPUT:

    - ``values`` - [val0, val1, val2, ...] or [(val0, lbl0),
      (val1,lbl1), ...] where all labels must be given or given as
      None.

    - ``label`` - a string (default: None); if given, this label
      is placed to the left of the entire button group

    - ``default`` - an object (default: 0); default value in values
      list

    - ``nrows`` - an integer (default: None); if given determines
      the number of rows of buttons; if given buttons option below
      is set to True

    - ``ncols`` - an integer (default: None); if given determines
      the number of columns of buttons; if given buttons option
      below is set to True

    - ``width`` - an integer (default: None); if given, all
      buttons are the same width, equal to this in HTML ex
      units's.

    - ``buttons`` - a bool (default: False); if True, use buttons

    EXAMPLES::

        sage: selector([1..5])    
        Drop down menu with 5 options
        sage: selector([1,2,7], default=2)
        Drop down menu with 3 options
        sage: selector([1,2,7], nrows=2)
        Button bar with 3 buttons
        sage: selector([1,2,7], ncols=2)
        Button bar with 3 buttons
        sage: selector([1,2,7], width=10)
        Drop down menu with 3 options
        sage: selector([1,2,7], buttons=True)
        Button bar with 3 buttons

    We create an :func:`interact` that involves computing charpolys of
    matrices over various rings::

        sage: @interact 
        ... def _(R=selector([ZZ,QQ,GF(17),RDF,RR]), n=(1..10)):
        ...      M = random_matrix(R, n)
        ...      show(M)
        ...      show(matrix_plot(M,cmap='Oranges'))
        ...      f = M.charpoly()
        ...      print f
        <html>...

    Here we create a drop-down::

        sage: @interact
        ... def _(a=selector([(2,'second'), (3,'third')])):
        ...       print a
        <html>...
    """
    if label is None:
        label=""

    if buttons:
        selector_type='buttons'
    else:
        selector_type='list'
        
    return Selector(default=default, label=label, selector_type=selector_type
                    nrows=nrows, ncols=ncols, width=width)

def input_grid(nrows, ncols, default=None, label=None, to_value=lambda x: x, width=4):
    r"""
    An input grid interactive control.  Use this in conjunction
    with the :func:`interact` command.

    INPUT:

    - ``nrows`` - an integer

    - ``ncols`` - an integer

    - ``default`` - an object; the default put in this input box

    - ``label`` - a string; the label rendered to the left of the
      box.

    - ``to_value`` - a list; the grid output (list of rows) is
      sent through this function.  This may reformat the data or
      coerce the type.

    - ``width`` - an integer; size of each input box in characters

    NOTEBOOK EXAMPLE::

        @interact
        def _(m = input_grid(2,2, default = [[1,7],[3,4]],
                             label='M=', to_value=matrix), 
              v = input_grid(2,1, default=[1,2],
                             label='v=', to_value=matrix)):
            try:
                x = m\v
                html('$$%s %s = %s$$'%(latex(m), latex(x), latex(v)))
            except:
                html('There is no solution to $$%s x=%s$$'%(latex(m), latex(v)))

    EXAMPLES::

        sage: input_grid(2,2, default = 0, label='M')
        Interact 2 x 2 input grid control labeled M with default value 0
        sage: input_grid(2,2, default = [[1,2],[3,4]], label='M')
        Interact 2 x 2 input grid control labeled M with default value [[1, 2], [3, 4]]
        sage: input_grid(2,2, default = [[1,2],[3,4]], label='M', to_value=MatrixSpace(ZZ,2,2))
        Interact 2 x 2 input grid control labeled M with default value [[1, 2], [3, 4]]
        sage: input_grid(1, 3, default=[[1,2,3]], to_value=lambda x: vector(flatten(x)))
        Interact 1 x 3 input grid control labeled None with default value [[1, 2, 3]]

    """
    if label is None:
        label = ""
    
    # TODO: implement to_value (which is very simlar to the input_box `type`)
    return InputGrid(nrows=nrows, ncols=ncols, width=width
                     default=default, label=label)    

def checkbox(default=True, label=None):
    """
    A checkbox interactive control.  Use this in conjunction with
    the :func:`interact` command.

    INPUT:

    - ``default`` - a bool (default: True); whether box should be
      checked or not

    - ``label`` - a string (default: None) text label rendered to
      the left of the box

    EXAMPLES::

        sage: checkbox(False, "Points")
        Interact checkbox labeled 'Points' with default value False
        sage: checkbox(True, "Points")
        Interact checkbox labeled 'Points' with default value True
        sage: checkbox(True)
        Interact checkbox labeled None with default value True
        sage: checkbox()
        Interact checkbox labeled None with default value True
    """
    if label is None:
        label=""
    return Checkbox(default=default, label=label)

def text_control(value=""):
    """
    Text that can be inserted among other :func:`interact` controls.

    INPUT:

    - ``value`` - HTML for the control

    EXAMPLES::

        sage: text_control('something')
        Text field: something
    """
    raise NotImplementedError

"""
text: http://www.sagemath.org/doc/reference/sagenb/notebook/interact.html#sagenb.notebook.interact.text_control
slider: 

http://www.sagemath.org/doc/reference/sagenb/notebook/interact.html#sagenb.notebook.interact.slider
 * display_value doesn't work
 * default value appears to be set correctly, but when the slider is
 moved, it shows that the slider was not in the right place and also
 appears that the default value wasn't even in the list of values.

range_slider: http://www.sagemath.org/doc/reference/sagenb/notebook/interact.html#sagenb.notebook.interact.range_slider



selector: http://www.sagemath.org/doc/reference/sagenb/notebook/interact.html#sagenb.notebook.interact.selector
input_grid: http://www.sagemath.org/doc/reference/sagenb/notebook/interact.html#sagenb.notebook.interact.input_grid
input_box: http://www.sagemath.org/doc/reference/sagenb/notebook/interact.html#sagenb.notebook.interact.input_box
color_selector: http://www.sagemath.org/doc/reference/sagenb/notebook/interact.html#sagenb.notebook.interact.color_selector
checkbox: http://www.sagemath.org/doc/reference/sagenb/notebook/interact.html#sagenb.notebook.interact.checkbox
"""