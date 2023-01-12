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
            if(status == false) {
                delete this.model[key];
            } else {
                if(multi) {
                    this.model[key] = ["Unspecified"];
                } else {
                    this.model[key] = "Unspecified";
                }
            }
        }
    },
    mounted() {
        addSkipLinks();
    },
    updated() {
        //console.log("Update!")
        //const fieldArray = this.$el.querySelectorAll('.vue-form-generator .form-group');
        //fieldArray.forEach(addSkipLink);
    }
});

function skipQuestion(ele) {
    // TODO: On skip, make sure triggered questions switch to Unspecified/skipped

    let newState = '';
    if(ele.innerHTML == 'SKIP') {
        newState = 'skip';
        ele.innerHTML = 'DISPLAY';
    } else {
        newState = 'display';
        ele.innerHTML = 'SKIP';
    }

    const labelElement = ele.parentElement;
    const group = labelElement.parentElement;
    if(group.classList.contains("field-radios")) {
        for (let i = 0; i < group.childNodes.length; i++) {
            let theNode = group.childNodes[i];
            if (theNode.nodeName == "DIV" && theNode.classList.contains("field-wrap")) {
                theNode.classList.toggle("hide");

                // When we hide a question, we also set the response to Unspecified
                let radioList = theNode.children[0];
                for(let j = 0; j < radioList.children.length; j++) {
                    if(radioList.children[j].innerText == "Unspecified") {
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
    } else if(group.classList.contains("field-checklist")) {
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
                    console.log(checkboxLabelElement);
                    if(checkboxLabelElement.innerText == "Unspecified") {
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
    } else {
        for (let i = 0; i < group.childNodes.length; i++) {
            let theNode = group.childNodes[i];
            if (theNode.nodeName == "DIV" && theNode.classList.contains("field-wrap")) {
                theNode.classList.toggle("hide");
                // TODO - ADD OTHER FIELD TYPES

                // When we hide a question, we also set the response to Unspecified
                let radioList = theNode.children[0];
                for(let j = 0; j < radioList.children.length; j++) {
                    if(radioList.children[j].innerText == "Unspecified") {
                        let unspecifiedElement = radioList.children[j];
                        for(let k = 0; k < unspecifiedElement.children.length; k++) {
                            if(unspecifiedElement.children[k].nodeName == "INPUT") {
                                if(unspecifiedElement.children[k].checked) {
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
}

/*
CODE TO UNSELECT RADIO BUTTON
document.getElementById('submit').onclick = function() {
    var radio = document.querySelector('input[type=radio][name=language]:checked');
    radio.checked = false;
}
*/

function addSkipLinks() {
    const fieldArray = document.getElementsByClassName("form-group");
//        const fieldArray = document.querySelectorAll('.vue-form-generator .form-group');
//        fieldArray.forEach(addSkipLink);
    for (i = 0; i < fieldArray.length; i++) {
        addSkipLink(fieldArray[i]);
    }
}

function addSkipLink(element) {
    // TODO: Figure out why it's only sometimes adding to the triggered questions

    // We don't want to provide the option of skipping the submit button
    if(!element.classList.contains("field-submit")) {
        for(let i = 0; i < element.children.length; i++) {
            if(element.children[i].nodeName == "LABEL") {
                let labelElement = element.children[i];
                if(!labelElement.innerHTML.includes("survey-skip")) {
                    labelElement.innerHTML = '<span class="survey-skip small-text" onClick="skipQuestion(this)">SKIP</span>' + labelElement.innerHTML;
                }
            }
        }
    }

    // We're going to hide "Unspecified" from view for all radio button groups
    if(element.classList.contains("field-radios")) {
        for(let i = 0; i < element.children.length; i++) {
            if(element.children[i].classList.contains("field-wrap")) {
                let fieldWrap = element.children[i];
                let radioList = fieldWrap.children[0];
                for(let j = 0; j < radioList.children.length; j++) {
                    if(radioList.children[j].innerText == "Unspecified") {
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
    if(element.classList.contains("field-checklist")) {
        for(let i = 0; i < element.children.length; i++) {
            if(element.children[i].classList.contains("field-wrap")) {
                let fieldWrap = element.children[i];
                let wrapper = fieldWrap.children[0];
                let listbox = wrapper.children[0];
                for(let j = 0; j < listbox.children.length; j++) {
                    if(listbox.children[j].innerText == "Unspecified") {
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
}

// This CANNOT be done in $(document).ready() on the page containing the vue form because
// the vue form is not created until after point :(
preventImplicitSubmission("survey_form");