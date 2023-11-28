def use_hook():
    try:
        from . import hook
        hook.hook_init()
    except BaseException:
        import traceback
        traceback.print_exc()