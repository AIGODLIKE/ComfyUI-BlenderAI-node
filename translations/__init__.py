from .translation import register, unregister


def i18n_register():
    register()


def i18n_unregister():
    unregister()
