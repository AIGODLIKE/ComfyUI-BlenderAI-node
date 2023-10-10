def linker_register():
    ...


def linker_unregister():
    ...


try:
    from VoronoiLinker import VoronoiOpBase, voronoiAnchorName, Prefs, GetNearestNodes, voronoiPreviewResultNdName
    from VoronoiLinker import GetNearestSockets, MinFromFgs, DoPreview, GetOpKey, ToolInvokeStencilPrepare, EditTreeIsNoneDrawCallback, VoronoiPreviewerDrawCallback
    from .linker import linker_register, linker_unregister
except BaseException:
    ...
