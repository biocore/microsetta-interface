"use strict";
//TODO FIXME HACK:  This is copied from Microsetta Admin - What are our plans
//for creating a common library shared across the microsetta projects?
//Potentially this file could be replaced with some existing javascript library
//but lacking a place for common code is frustrating.

//Attempts to simplify complex business logic into easily verified expressions

//Example: We should send email upon adding a scan if and only if
//The sample status has changed AND the send_email checkbox is ticked.

class NamedExpression{
    constructor(name, value) {
        this.onChange = [];
        this.name = name;
        this._value = value;
    }

    get value(){
        return this._value;
    }

    set value(v){
        if (v !== this._value){
            this._value = v;
            for (var i = 0; i < this.onChange.length; i++){
                this.onChange[i].update();
            }
        }
    }

    register(obs){
        this.onChange.push(obs);
    }

    update(){

    }
}

class JQuerySelectInput extends NamedExpression {
    constructor(name, selector){
        super(name, $(selector).val());
        var self = this;
        this.selector = selector;

        $(selector).change(function(){
            self.value = $(this).val();
        })
    }
}

class JQueryCheckboxInput extends NamedExpression {
    constructor(name, selector){
        super(name, $(selector).prop("checked"));
        var self = this;
        this.selector = selector;

        $(selector).change(function(){
            self.value = this.checked;
        })
    }
}

class AndExpression extends NamedExpression {
    constructor(A, B) {
        super("(" + A.name + " AND " + B.name + ")", A.value && B.value);
        A.register(this);
        B.register(this);
        this.A = A;
        this.B = B;
    }

    update(){
        this.value = this.A.value && this.B.value;
    }
}

class OrExpression extends NamedExpression {
    constructor(A, B){
        super("(" +A.name + " OR " + B.name + ")", A.value || B.value);
        A.register(this);
        B.register(this);
        this.A = A;
        this.B = B;
    }

    update(){
        this.value = this.A.value || this.B.value;
    }
}

class NotExpression extends NamedExpression {
    constructor(A){
        super("!" + A.name, !A.value);
        A.register(this);
        this.A = A;
    }

    update(){
        this.value = !this.A.value;
    }
}

class EqualsExpression extends NamedExpression {
    constructor(A, B){
        super("(" + A.name + " === " + B.name + ")", A.value === B.value);
        A.register(this);
        B.register(this);
        this.A = A;
        this.B = B;
    }

    update() {
        this.value = (this.A.value === this.B.value);
    }
}

class JQueryOutput {
    constructor(X, selector, property){
        this.X = X;
        this.selector = selector;
        this.prop = property;

        X.register(this);
        $(selector).prop(property, X.value);
    }

    update()
    {
        $(this.selector).prop(this.prop, this.X.value);
    }
}

class DelegateOutput {
    constructor(onChanged, ...observed) {
        this.onChanged = onChanged;
        this.observed = observed;

        for (var i = 0; i < observed.length; i++)
            observed[i].register(this);

        this.update();
    }

    update()
    {
        var vals = [];
        for (var i = 0; i < this.observed.length; i++)
            vals.push(this.observed[i].value);
        this.onChanged(...vals);
    }
}

class ConsoleOutput {
    constructor(X) {
        this.X = X;
        console.log("On Init: " + this.X.name + ": " + this.X.value);

        X.register(this);
    }

    update()
    {
        console.log(this.X.name + ": " + this.X.value);
    }
}

if (typeof module !== 'undefined' && typeof module.exports !== 'undefined'){
  module.exports = {
    "NamedExpression": NamedExpression,
    "AndExpression": AndExpression,
    "OrExpression": OrExpression,
    "NotExpression": NotExpression,
    "EqualsExpression": EqualsExpression,
    "DelegateOutput": DelegateOutput
  };
}
