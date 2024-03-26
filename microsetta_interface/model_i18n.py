from collections import namedtuple

from flask_babel import gettext
import copy


EN_US_KEY = "en_us"
ES_MX_KEY = "es_mx"
ES_ES_KEY = "es_es"
JA_JP_KEY = "ja_jp"

Lang = namedtuple('Lang', ['value', 'display_text'])
LANGUAGES = {
    EN_US_KEY: Lang("en_US", "English"),
    ES_MX_KEY: Lang("es_MX", "Español (México)"),
    ES_ES_KEY: Lang("es_ES", "Español (España)")
}

# We need a default full locale when a user's browser only sends a partial
# value. At the moment, es is the only ambiguous situation we need to deal
# with, and we'll default to es_ES since THDMI Spain was the more recent
# Spanish-speaking campaign. I suspect we'll want to revise this to es_MX for
# relaunch.
PARTIAL_TO_FULL_LOCALES = {
    "en": "en_US",
    "es": "es_ES",
    "ja": "ja_JP"
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
    i18n_survey_template["description"] = \
        gettext(survey_template["description"])
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
    gettext("Basic Information")
    gettext("At Home")
    gettext("Lifestyle")
    gettext("Gut")
    gettext("General Health")
    gettext("Health Diagnosis")
    gettext("Allergies")
    gettext("Diet")
    gettext("Detailed Diet")
    gettext("Other")
    gettext("Polyphenols")
    gettext("Spain FFQ")

    # Survey descriptions
    # Intentionally skipping MyFoodRepo since it's only for US residents
    gettext("Polyphenols are chemical compounds naturally found in plants "
            "that have been shown to provide many beneficial properties. "
            "They are antioxidants, fighting aging and protecting your heart"
            ", but they may also provide benefits by interacting with the "
            "microbes in your gut. This survey will allow us to better "
            "quantify your consumption of polyphenols through your diet.")
    gettext("<strong>Only for participants in Spain:</strong><br />"
            "The Food Frequency Questionnaire (FFQ) will ask you about your "
            "usual frequency of consumption of a list of foods and beverages."
            " The questionnaire consists of 28 questions, and will allow us "
            "to find out what your usual diet is like.")

    # Ensure that EN_US_KEY is added to the POT file
    gettext("en_us")
