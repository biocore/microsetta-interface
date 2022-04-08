import googletrans
import polib
import click


@click.command()
@click.option('--pofile', help='The file to translate',
              type=click.Path(exists=True), required=True)
@click.option('--locale', help='The locale to translate into', type=str,
              required=True)
@click.option('--output', help='A file to save into (if not specified, '
              'saves inplace)', required=False, type=click.Path(exists=False))
def trans(pofile, locale, output):
    # verify the locale name is in the path of the pofile
    assert locale in pofile
    pofile = polib.pofile(pofile)

    # example interaction based on https://github.com/Brandon1016/poTranslate (MIT license)
    translator = googletrans.Translator()
    entries = pofile.untranslated_entries()
    entries.extend(pofile.fuzzy_entries())
    for entry in pofile.untranslated_entries():
        print(entry.msgid)
        translated = translator.translate(entry.msgid, dest=locale)
        entry.msgstr = translated.text
        entry.flags.append('fuzzy')

    if output is not None:
        pofile.save(output)
    else:
        pofile.save()


if __name__ == '__main__':
    trans()
