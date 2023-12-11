def use_hook(action=True):
    try:
        from . import hook
        if action:
            hook.hook_init()
        else:
            hook.hook_uninit()
    except BaseException:
        import traceback
        traceback.print_exc()
