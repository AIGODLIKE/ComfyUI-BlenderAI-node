import bpy
from .translation import translations_dict


def i18n_register():
    bpy.app.translations.register(__name__, translations_dict)


def i18n_unregister():
    bpy.app.translations.unregister(__name__)
