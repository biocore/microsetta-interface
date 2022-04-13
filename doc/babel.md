# To update translation files

```bash
cd microsetta-interface
pybabel extract -F ../babel.cfg -o translations/base.pot .
pybabel update -i translations/base.pot -d translations
```

# To generate naive automatic translations

GTranslate translations can be generated with the following. These should undergo a sanity check as, in particular, countries may get translated unusually and it will stand out. Automated entries are remarked as fuzzy and will be flagged as such in POEdit.

The translation script has been tested with polib==1.1.1 and googletrans==3.1.0a0, installable from pypi.

```
python naive_translate.py --pofile path/to/the/pofile --locale locale_to_translate_into --output path/to/new/pofile
```
