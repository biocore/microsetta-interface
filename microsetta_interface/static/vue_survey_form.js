var vm = new Vue({
    el: "#app",

    components: {
        "vue-form-generator": VueFormGenerator.component
    },

    data() {
        return {
            model: survey_model,
            schema: survey_schema,
            formOptions: {
                validateAfterLoad: true,
                validateAfterChanged: true
            }
        };
    },

    methods: {
        prettyJSON: function(json) {
            if (json) {
                json = JSON.stringify(json, undefined, 4);
                json = json.replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>');
                return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function(match) {
                    var cls = 'number';
                    if (/^"/.test(match)) {
                        if (/:$/.test(match)) {
                            cls = 'key';
                        } else {
                            cls = 'string';
                        }
                    } else if (/true|false/.test(match)) {
                        cls = 'boolean';
                    } else if (/null/.test(match)) {
                        cls = 'null';
                    }
                    return '<span class="' + cls + '">' + match + '</span>';
                });
            }
        },
        methodToUpdate(key, status, multi) {
            /*
            Questions 108 and 113 are Height and Weight respectively. Since
            they're numeric values, it would be inappropriate to use
            Unspecified or any other text value to denote they've been skipped.
            */

            if(status == false) {
                if(key == '108' || key == '113') {
                    this.model[key] = "";
                } else {
                    delete this.model[key];
                }
            } else {
                if(multi) {
                    this.model[key] = [UNSPECIFIED];
                } else {
                    if(key == '108' || key == '113') {
                        this.model[key] = 0;
                    } else {
                        this.model[key] = UNSPECIFIED;
                    }
                }
            }
        }
    },
    mounted() {
        addSkipLinks();
    },
});

function skipQuestion(ele, skipType="user-input") {
    var group;
    var labelElement;
    let newState = '';
    if(skipType == "user-input") {
        if(ele.innerHTML == SKIP) {
            newState = 'skip';
            ele.innerHTML = DISPLAY;
        } else {
            newState = 'display';
            ele.innerHTML = SKIP;
        }

        const spanElement = ele.parentElement;
        labelElement = spanElement.parentElement;
        group = labelElement.parentElement;
    } else {
        labelElement = ele;
        const spanElement = ele.children[0];
        const skipSpanElement = spanElement.children[0];
        skipSpanElement.innerHTML = DISPLAY;
        group = ele.parentElement;
        newState = 'skip';
    }
    if(group.classList.contains("field-radios")) {
        skipRadioField(group, labelElement, newState);
    } else if(group.classList.contains("field-checklist")) {
        skipChecklistField(group, labelElement, newState);
    } else if(group.classList.contains("field-input") ) {
        skipInputField(group, labelElement, newState);
    } else if(group.classList.contains("field-textArea")) {
        skipTextareaField(group, labelElement, newState);
    } else if(group.classList.contains("field-select")) {
        skipSelectField(group, labelElement, newState);
    }
}

function addSkipLinks() {
    const fieldArray = document.getElementsByClassName("form-group");
    for (i = 0; i < fieldArray.length; i++) {
        addSkipLink(fieldArray[i]);
    }
}

function addSkipLink(element) {
    // We're going to hide "Unspecified" from view for all radio button groups
    if(element.classList.contains("field-radios")) {
        for(let i = 0; i < element.children.length; i++) {
            if(element.children[i].classList.contains("field-wrap")) {
                let fieldWrap = element.children[i];
                let radioList = fieldWrap.children[0];
                for(let j = 0; j < radioList.children.length; j++) {
                    if(radioList.children[j].innerText == UNSPECIFIED) {
                        let unspecifiedElement = radioList.children[j];
                        unspecifiedElement.style.position = "absolute";
                        unspecifiedElement.style.top = "-9999px";
                        unspecifiedElement.style.left = "-9999px";
                        unspecifiedElement.style.display = "inline-block";
                    }
                }
            }
        }
    }

    // We're going to hide "Unspecified" from view for all checkbox groups
    else if(element.classList.contains("field-checklist")) {
        for(let i = 0; i < element.children.length; i++) {
            if(element.children[i].classList.contains("field-wrap")) {
                let fieldWrap = element.children[i];
                let wrapper = fieldWrap.children[0];
                let listbox = wrapper.children[0];
                for(let j = 0; j < listbox.children.length; j++) {
                    if(listbox.children[j].innerText == UNSPECIFIED) {
                        let unspecifiedElement = listbox.children[j];
                        unspecifiedElement.style.position = "absolute";
                        unspecifiedElement.style.top = "-9999px";
                        unspecifiedElement.style.left = "-9999px";
                        unspecifiedElement.style.display = "inline-block";
                    }
                }
            }
        }
    }

    else if(element.classList.contains("field-select")) {
        for(let i = 0; i < element.children.length; i++) {
            if(element.children[i].classList.contains("field-wrap")) {
                let fieldWrap = element.children[i];
                let selectElement = fieldWrap.children[0];
                for(let j = 0; j < selectElement.children.length; j++) {
                    if(selectElement.children[j].value == UNSPECIFIED) {
                        selectElement.children[j].hidden = "true";
                    }
                }
            }
        }
    }
}

function skipRadioField(group, labelElement, newState) {
    for (let i = 0; i < group.childNodes.length; i++) {
        let theNode = group.childNodes[i];
        if (theNode.nodeName == "DIV" && theNode.classList.contains("field-wrap")) {
            theNode.classList.toggle("hide");

            // When we hide a question, we also set the response to Unspecified
            let radioList = theNode.children[0];
            for(let j = 0; j < radioList.children.length; j++) {
                if(radioList.children[j].innerText == UNSPECIFIED) {
                    let unspecifiedElement = radioList.children[j];
                    for(let k = 0; k < unspecifiedElement.children.length; k++) {
                        if(unspecifiedElement.children[k].nodeName == "INPUT") {
                            if(newState == 'display') {
                                unspecifiedElement.children[k].checked = false;
                                vm.methodToUpdate(unspecifiedElement.children[k].name, false, false)
                            } else {
                                unspecifiedElement.children[k].checked = true;
                                vm.methodToUpdate(unspecifiedElement.children[k].name, true, false)
                            }
                            unspecifiedElement.classList.toggle("is-checked");
                        }
                    }
                }
            }
        }
    }
}

function skipChecklistField(group, labelElement, newState) {
    let fieldId = labelElement.htmlFor;
    for (let i = 0; i < group.childNodes.length; i++) {
        let theNode = group.childNodes[i];
        if (theNode.nodeName == "DIV" && theNode.classList.contains("field-wrap")) {
            theNode.classList.toggle("hide");
            let wrapper = theNode.children[0];
            let listbox = wrapper.children[0];

            // When we hide a question, we also set the response to Unspecified
            for(let j = 0; j < listbox.children.length; j++) {
                let listRow = listbox.children[j];
                let checkboxLabelElement = listRow.children[0];
                if(checkboxLabelElement.innerText == UNSPECIFIED) {
                    for(let k = 0; k < checkboxLabelElement.children.length; k++) {
                        if(checkboxLabelElement.children[k].nodeName == "INPUT") {
                            if(newState == 'skip') {
                                checkboxLabelElement.children[k].checked = true;
                                vm.methodToUpdate(fieldId, true, true)
                            } else {
                                checkboxLabelElement.children[k].checked = false;
                                vm.methodToUpdate(fieldId, false, true)
                            }
                        }
                    }
                    checkboxLabelElement.classList.toggle("is-checked");
                } else {
                    for(let k = 0; k < checkboxLabelElement.children.length; k++) {
                        if(checkboxLabelElement.children[k].nodeName == "INPUT") {
                            checkboxLabelElement.children[k].checked = false;
                        }
                    }
                    if(checkboxLabelElement.classList.contains("is-checked")) {
                        checkboxLabelElement.classList.toggle("is-checked");
                    }
                }
            }
        }
    }
}

function skipInputField(group, labelElement, newState) {
    for (let i = 0; i < group.childNodes.length; i++) {
        let theNode = group.childNodes[i];
        if (theNode.nodeName == "DIV" && theNode.classList.contains("field-wrap")) {
            let wrapper = theNode.children[0];
            let inputElement = wrapper.children[0];

            if(newState == "display") {
                theNode.style.display = "";
                inputElement.value = "";
                vm.methodToUpdate(inputElement.name, false, false);
            } else {
                theNode.style.display = "none";
                inputElement.value = UNSPECIFIED;
                vm.methodToUpdate(inputElement.name, true, false);
            }
        }
    }
}

function skipTextareaField(group, labelElement, newState) {
    for (let i = 0; i < group.childNodes.length; i++) {
        let theNode = group.childNodes[i];
        if (theNode.nodeName == "DIV" && theNode.classList.contains("field-wrap")) {
            let inputElement = theNode.children[0];

            if(newState == "display") {
                theNode.style.display = "";
                inputElement.innerText = "";
                vm.methodToUpdate(inputElement.name, false, false);
            } else {
                theNode.style.display = "none";
                inputElement.innerText = UNSPECIFIED;
                vm.methodToUpdate(inputElement.name, true, false);
            }
        }
    }
}

function skipSelectField(group, labelElement, newState) {
    for(let i = 0; i < group.childNodes.length; i++) {
        let theNode = group.childNodes[i];
        if (theNode.nodeName == "DIV" && theNode.classList.contains("field-wrap")) {
            let inputElement = theNode.children[0];

            if(newState == "display") {
                theNode.style.display = "";
                inputElement.selectedIndex = -1;
                vm.methodToUpdate(inputElement.name, false, false);
            } else {
                theNode.style.display = "none";
                inputElement.selectedIndex = 0;
                vm.methodToUpdate(inputElement.name, true, false);
            }
        }
    }
}

// This CANNOT be done in $(document).ready() on the page containing the vue form because
// the vue form is not created until after point :(
preventImplicitSubmission("survey_form");