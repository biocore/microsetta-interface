from collections import namedtuple

from flask_babel import gettext
import copy


EN_US_KEY = "en_us"
ES_MX_KEY = "es_mx"

Lang = namedtuple('Lang', ['value', 'display_text'])
LANGUAGES = {
    EN_US_KEY: Lang("en_US", "English"),
    ES_MX_KEY: Lang("es_MX", "Español")
}


def translate_sample(sample):
    i18n_sample = copy.deepcopy(sample)
    i18n_sample["sample_site"] = gettext(sample["sample_site"])
    if i18n_sample["sample_site"] is None:
        i18n_sample["sample_site"] = ""
    if i18n_sample["sample_datetime"] is None:
        i18n_sample["sample_datetime"] = ""
    return i18n_sample


def translate_source(source):
    i18n_source = copy.deepcopy(source)
    i18n_source["source_type"] = gettext(source["source_type"])
    return i18n_source


def translate_survey_template(survey_template):
    i18n_survey_template = copy.deepcopy(survey_template)
    i18n_survey_template["survey_template_title"] = \
        gettext(survey_template["survey_template_title"])
    return i18n_survey_template


def declare_enum_values():
    # There are a few enum fields in the private api
    # model object types that need to be translated
    # We define those enum values here so that babel
    # picks them up for translation.

    # Sample.sample_site
    #     sample_site:
    #       enum: ["Blood (skin prick)", "Saliva", "Ear wax", "Forehead",
    #       "Fur", "Hair", "Left hand", "Left leg", "Mouth", "Nares",
    #       "Nasal mucus", "Right hand", "Right leg", "Stool", "Tears",
    #       "Torso", "Vaginal mucus", null]
    gettext("Blood (skin prick)")
    gettext("Saliva")
    gettext("Ear wax")
    gettext("Forehead")
    gettext("Fur")
    gettext("Hair")
    gettext("Left hand")
    gettext("Left leg")
    gettext("Mouth")
    gettext("Nares")
    gettext("Nasal mucus")
    gettext("Right hand")
    gettext("Right leg")
    gettext("Stool")
    gettext("Tears")
    gettext("Torso")
    gettext("Vaginal mucus")

    # Source.source_site:
    # source_type:
    # enum: [human, animal, environmental]
    gettext("human")
    gettext("animal")
    gettext("environmental")

    # SurveyTemplate.survey_template_title:
    # Not defined in the microsetta-private-api yaml at the moment
    # Taken from survey_template_repo.py
    gettext("Primary Questionnaire")
    gettext("Pet Information")
    gettext("Fermented Foods Questionnaire")
    gettext("Surfer Questionnaire")
    gettext("Personal Microbiome Information")
    gettext("COVID-19 Questionnaire")
    gettext("Vioscreen Food Frequency Questionnaire")

    # Ensure that EN_US_KEY is added to the POT file
    gettext("en_us")
