"""An OpenGL context that never shows a window: nothing on screen, in the taskbar or in the
dock. Renders go through an FBO, so the context's own drawable is never drawn to.

The context is created with the API PyOpenGL loads its functions from (GLX, EGL, WGL or
CGL), so the functions it resolves match the current context."""

import ctypes
import ctypes.util
import sys
from contextlib import contextmanager
from typing import Any, Iterator

from OpenGL import platform as gl_platform

PLATFORM: Any = gl_platform.PLATFORM


class GLContextError(RuntimeError):
    pass


def _fn(lib: Any, name: str, restype: Any, *argtypes: Any) -> Any:
    function = getattr(lib, name)
    function.restype, function.argtypes = restype, argtypes
    return function


def _attribs(values: dict[int, int], end: int = 0) -> Any:
    flat = [item for pair in values.items() for item in pair]
    return (ctypes.c_int * (len(flat) + 1))(*flat, end)


@contextmanager
def offscreen_context() -> Iterator[None]:
    """Makes a hidden OpenGL context current for the duration of the block."""
    match type(PLATFORM).__name__:
        case "GLXPlatform":
            create = _glx_context
        case "EGLPlatform":
            create = _egl_context
        case "Win32Platform":
            create = _wgl_context
        case "DarwinPlatform":
            create = _cgl_context
        case name:
            raise GLContextError(f"Unsupported PyOpenGL platform {name}")
    with create():
        yield


# the libraries are loaded again so the signatures set here don't clash with PyOpenGL's


@contextmanager
def _glx_context() -> Iterator[None]:
    # an X window that is never mapped is never shown, and override_redirect keeps the
    # window manager away from it. Mesa's software GLX (xvfb) has no pbuffers.
    GLX_WINDOW_BIT = 0x1
    GLX_RGBA_BIT = 0x1
    GLX_RED_SIZE = 8
    GLX_GREEN_SIZE = 9
    GLX_BLUE_SIZE = 10
    GLX_ALPHA_SIZE = 11
    GLX_DEPTH_SIZE = 12
    GLX_DRAWABLE_TYPE = 0x8010
    GLX_RENDER_TYPE = 0x8011
    GLX_RGBA_TYPE = 0x8014
    CW_BORDER_PIXEL = 1 << 3
    CW_OVERRIDE_REDIRECT = 1 << 9
    CW_COLORMAP = 1 << 13
    INPUT_OUTPUT = 1
    ALLOC_NONE = 0

    p = ctypes.c_void_p
    ulong = ctypes.c_ulong

    class XVisualInfo(ctypes.Structure):
        _fields_ = [
            ("visual", p),
            ("visualid", ulong),
            ("screen", ctypes.c_int),
            ("depth", ctypes.c_int),
            ("class_", ctypes.c_int),
            ("red_mask", ulong),
            ("green_mask", ulong),
            ("blue_mask", ulong),
            ("colormap_size", ctypes.c_int),
            ("bits_per_rgb", ctypes.c_int),
        ]

    class XSetWindowAttributes(ctypes.Structure):
        _fields_ = [
            ("background_pixmap", ulong),
            ("background_pixel", ulong),
            ("border_pixmap", ulong),
            ("border_pixel", ulong),
            ("bit_gravity", ctypes.c_int),
            ("win_gravity", ctypes.c_int),
            ("backing_store", ctypes.c_int),
            ("backing_planes", ulong),
            ("backing_pixel", ulong),
            ("save_under", ctypes.c_int),
            ("event_mask", ctypes.c_long),
            ("do_not_propagate_mask", ctypes.c_long),
            ("override_redirect", ctypes.c_int),
            ("colormap", ulong),
            ("cursor", ulong),
        ]

    x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
    glx = ctypes.CDLL(PLATFORM.GLX._name)
    c_int, int_pointer = ctypes.c_int, ctypes.POINTER(ctypes.c_int)
    XOpenDisplay = _fn(x11, "XOpenDisplay", p, ctypes.c_char_p)
    XCloseDisplay = _fn(x11, "XCloseDisplay", c_int, p)
    XDefaultScreen = _fn(x11, "XDefaultScreen", c_int, p)
    XRootWindow = _fn(x11, "XRootWindow", ulong, p, c_int)
    XFree = _fn(x11, "XFree", c_int, p)
    XCreateColormap = _fn(x11, "XCreateColormap", ulong, p, ulong, p, c_int)
    XFreeColormap = _fn(x11, "XFreeColormap", c_int, p, ulong)
    XCreateWindow = _fn(
        x11,
        "XCreateWindow",
        ulong,
        p,
        ulong,
        c_int,
        c_int,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_uint,
        c_int,
        ctypes.c_uint,
        p,
        ulong,
        ctypes.POINTER(XSetWindowAttributes),
    )
    XDestroyWindow = _fn(x11, "XDestroyWindow", c_int, p, ulong)
    glXChooseFBConfig = _fn(
        glx, "glXChooseFBConfig", ctypes.POINTER(p), p, c_int, int_pointer, int_pointer
    )
    glXGetVisualFromFBConfig = _fn(
        glx, "glXGetVisualFromFBConfig", ctypes.POINTER(XVisualInfo), p, p
    )
    glXCreateWindow = _fn(glx, "glXCreateWindow", ulong, p, p, ulong, int_pointer)
    glXDestroyWindow = _fn(glx, "glXDestroyWindow", None, p, ulong)
    glXCreateNewContext = _fn(glx, "glXCreateNewContext", p, p, p, c_int, p, c_int)
    glXDestroyContext = _fn(glx, "glXDestroyContext", None, p, p)
    glXMakeContextCurrent = _fn(glx, "glXMakeContextCurrent", c_int, p, ulong, ulong, p)

    display = XOpenDisplay(None)
    if not display:
        raise GLContextError(
            "Cannot open the X display, run under a display server or xvfb-run"
        )
    try:
        screen = XDefaultScreen(display)
        count = ctypes.c_int()
        configs = glXChooseFBConfig(
            display,
            screen,
            _attribs(
                {
                    GLX_DRAWABLE_TYPE: GLX_WINDOW_BIT,
                    GLX_RENDER_TYPE: GLX_RGBA_BIT,
                    GLX_RED_SIZE: 8,
                    GLX_GREEN_SIZE: 8,
                    GLX_BLUE_SIZE: 8,
                    GLX_ALPHA_SIZE: 8,
                    GLX_DEPTH_SIZE: 24,
                }
            ),
            ctypes.byref(count),
        )
        if not configs or count.value == 0:
            raise GLContextError("No GLX framebuffer config for OpenGL")
        config = configs[0]
        XFree(configs)
        visual_info = glXGetVisualFromFBConfig(display, config)
        if not visual_info:
            raise GLContextError("No X visual for the GLX framebuffer config")
        visual, depth = visual_info.contents.visual, visual_info.contents.depth
        XFree(visual_info)

        root = XRootWindow(display, screen)
        colormap = XCreateColormap(display, root, visual, ALLOC_NONE)
        attributes = XSetWindowAttributes(colormap=colormap, override_redirect=True)
        # never XMapWindow'd
        window = XCreateWindow(
            display, root, 0, 0, 1, 1, 0, depth, INPUT_OUTPUT, visual,
            CW_BORDER_PIXEL | CW_OVERRIDE_REDIRECT | CW_COLORMAP,
            ctypes.byref(attributes),
        )  # fmt: skip
        try:
            gl_window = glXCreateWindow(display, config, window, None)
            context = glXCreateNewContext(display, config, GLX_RGBA_TYPE, None, True)
            if not gl_window or not context:
                raise GLContextError("Cannot create the GLX context")
            try:
                if not glXMakeContextCurrent(display, gl_window, gl_window, context):
                    raise GLContextError("Cannot make the GLX context current")
                try:
                    yield
                finally:
                    glXMakeContextCurrent(display, 0, 0, None)
            finally:
                glXDestroyContext(display, context)
                glXDestroyWindow(display, gl_window)
        finally:
            XDestroyWindow(display, window)
            XFreeColormap(display, colormap)
    finally:
        XCloseDisplay(display)


@contextmanager
def _egl_context() -> Iterator[None]:
    # EGL renders without any drawable (surfaceless) or into a 1x1 pbuffer
    EGL_PBUFFER_BIT = 0x1
    EGL_OPENGL_BIT = 0x8
    EGL_ALPHA_SIZE = 0x3021
    EGL_BLUE_SIZE = 0x3022
    EGL_GREEN_SIZE = 0x3023
    EGL_RED_SIZE = 0x3024
    EGL_DEPTH_SIZE = 0x3025
    EGL_SURFACE_TYPE = 0x3033
    EGL_NONE = 0x3038
    EGL_RENDERABLE_TYPE = 0x3040
    EGL_EXTENSIONS = 0x3055
    EGL_HEIGHT = 0x3056
    EGL_WIDTH = 0x3057
    EGL_OPENGL_API = 0x30A2
    EGL_PLATFORM_SURFACELESS_MESA = 0x31DD

    egl = ctypes.CDLL(PLATFORM.EGL._name)
    p = ctypes.c_void_p
    c_uint, int_pointer = ctypes.c_uint, ctypes.POINTER(ctypes.c_int)
    eglGetDisplay = _fn(egl, "eglGetDisplay", p, p)
    eglQueryString = _fn(egl, "eglQueryString", ctypes.c_char_p, p, ctypes.c_int)
    eglGetProcAddress = _fn(egl, "eglGetProcAddress", p, ctypes.c_char_p)
    eglInitialize = _fn(egl, "eglInitialize", c_uint, p, p, p)
    eglTerminate = _fn(egl, "eglTerminate", c_uint, p)
    eglBindAPI = _fn(egl, "eglBindAPI", c_uint, c_uint)
    eglChooseConfig = _fn(
        egl,
        "eglChooseConfig",
        c_uint,
        p,
        int_pointer,
        ctypes.POINTER(p),
        ctypes.c_int,
        int_pointer,
    )
    eglCreatePbufferSurface = _fn(egl, "eglCreatePbufferSurface", p, p, p, int_pointer)
    eglDestroySurface = _fn(egl, "eglDestroySurface", c_uint, p, p)
    eglCreateContext = _fn(egl, "eglCreateContext", p, p, p, p, int_pointer)
    eglDestroyContext = _fn(egl, "eglDestroyContext", c_uint, p, p)
    eglMakeCurrent = _fn(egl, "eglMakeCurrent", c_uint, p, p, p, p)

    display = eglGetDisplay(None)
    if not display or not eglInitialize(display, None, None):
        # no display server at all: Mesa can still render without one
        client_extensions = eglQueryString(None, EGL_EXTENSIONS) or b""
        address = eglGetProcAddress(b"eglGetPlatformDisplayEXT")
        if b"EGL_MESA_platform_surfaceless" not in client_extensions or not address:
            raise GLContextError("Cannot initialize an EGL display")
        eglGetPlatformDisplayEXT = ctypes.CFUNCTYPE(p, c_uint, p, int_pointer)(address)
        display = eglGetPlatformDisplayEXT(EGL_PLATFORM_SURFACELESS_MESA, None, None)
        if not display or not eglInitialize(display, None, None):
            raise GLContextError("Cannot initialize an EGL display")
    try:
        if not eglBindAPI(EGL_OPENGL_API):
            raise GLContextError("EGL has no desktop OpenGL")
        extensions = eglQueryString(display, EGL_EXTENSIONS) or b""
        surfaceless = b"EGL_KHR_surfaceless_context" in extensions
        config = p()
        count = ctypes.c_int()
        eglChooseConfig(
            display,
            _attribs(
                {
                    EGL_SURFACE_TYPE: 0 if surfaceless else EGL_PBUFFER_BIT,
                    EGL_RENDERABLE_TYPE: EGL_OPENGL_BIT,
                    EGL_RED_SIZE: 8,
                    EGL_GREEN_SIZE: 8,
                    EGL_BLUE_SIZE: 8,
                    EGL_ALPHA_SIZE: 8,
                    EGL_DEPTH_SIZE: 24,
                },
                end=EGL_NONE,
            ),
            ctypes.byref(config),
            1,
            ctypes.byref(count),
        )
        if count.value == 0:
            raise GLContextError("No EGL config for desktop OpenGL")
        surface = None
        if not surfaceless:
            surface = eglCreatePbufferSurface(
                display, config, _attribs({EGL_WIDTH: 1, EGL_HEIGHT: 1}, end=EGL_NONE)
            )
            if not surface:
                raise GLContextError("Cannot create the EGL pbuffer")
        try:
            context = eglCreateContext(display, config, None, None)
            if not context:
                raise GLContextError("Cannot create the EGL context")
            try:
                if not eglMakeCurrent(display, surface, surface, context):
                    raise GLContextError("Cannot make the EGL context current")
                try:
                    yield
                finally:
                    eglMakeCurrent(display, None, None, None)
            finally:
                eglDestroyContext(display, context)
        finally:
            if surface:
                eglDestroySurface(display, surface)
    finally:
        eglTerminate(display)


@contextmanager
def _wgl_context() -> Iterator[None]:
    # WGL needs a window's device context, but a window that is never shown has no
    # taskbar button and never appears (WS_EX_TOOLWINDOW keeps it out of alt-tab too)
    CS_OWNDC = 0x20
    WS_POPUP = 0x80000000
    WS_EX_TOOLWINDOW = 0x80
    PFD_DRAW_TO_WINDOW = 0x4
    PFD_SUPPORT_OPENGL = 0x20
    PFD_TYPE_RGBA = 0

    assert sys.platform == "win32"
    from ctypes import wintypes

    class PIXELFORMATDESCRIPTOR(ctypes.Structure):
        _fields_ = [
            ("nSize", wintypes.WORD),
            ("nVersion", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("iPixelType", wintypes.BYTE),
            ("cColorBits", wintypes.BYTE),
            ("cRedBits", wintypes.BYTE),
            ("cRedShift", wintypes.BYTE),
            ("cGreenBits", wintypes.BYTE),
            ("cGreenShift", wintypes.BYTE),
            ("cBlueBits", wintypes.BYTE),
            ("cBlueShift", wintypes.BYTE),
            ("cAlphaBits", wintypes.BYTE),
            ("cAlphaShift", wintypes.BYTE),
            ("cAccumBits", wintypes.BYTE),
            ("cAccumRedBits", wintypes.BYTE),
            ("cAccumGreenBits", wintypes.BYTE),
            ("cAccumBlueBits", wintypes.BYTE),
            ("cAccumAlphaBits", wintypes.BYTE),
            ("cDepthBits", wintypes.BYTE),
            ("cStencilBits", wintypes.BYTE),
            ("cAuxBuffers", wintypes.BYTE),
            ("iLayerType", wintypes.BYTE),
            ("bReserved", wintypes.BYTE),
            ("dwLayerMask", wintypes.DWORD),
            ("dwVisibleMask", wintypes.DWORD),
            ("dwDamageMask", wintypes.DWORD),
        ]

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", ctypes.c_void_p),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    kernel32 = ctypes.WinDLL("kernel32")
    user32 = ctypes.WinDLL("user32")
    gdi32 = ctypes.WinDLL("gdi32")
    opengl32 = ctypes.WinDLL(PLATFORM.GL._name)
    p = ctypes.c_void_p
    BOOL, c_int = wintypes.BOOL, ctypes.c_int
    pfd_pointer = ctypes.POINTER(PIXELFORMATDESCRIPTOR)
    GetModuleHandleW = _fn(kernel32, "GetModuleHandleW", p, wintypes.LPCWSTR)
    RegisterClassW = _fn(
        user32, "RegisterClassW", wintypes.ATOM, ctypes.POINTER(WNDCLASSW)
    )
    UnregisterClassW = _fn(user32, "UnregisterClassW", BOOL, wintypes.LPCWSTR, p)
    CreateWindowExW = _fn(
        user32,
        "CreateWindowExW",
        p,
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        c_int,
        c_int,
        c_int,
        c_int,
        p,
        p,
        p,
        p,
    )
    DestroyWindow = _fn(user32, "DestroyWindow", BOOL, p)
    GetDC = _fn(user32, "GetDC", p, p)
    ReleaseDC = _fn(user32, "ReleaseDC", c_int, p, p)
    ChoosePixelFormat = _fn(gdi32, "ChoosePixelFormat", c_int, p, pfd_pointer)
    SetPixelFormat = _fn(gdi32, "SetPixelFormat", BOOL, p, c_int, pfd_pointer)
    wglCreateContext = _fn(opengl32, "wglCreateContext", p, p)
    wglDeleteContext = _fn(opengl32, "wglDeleteContext", BOOL, p)
    wglMakeCurrent = _fn(opengl32, "wglMakeCurrent", BOOL, p, p)

    instance = GetModuleHandleW(None)
    class_name = "ModelResolverOffscreen"
    window_class = WNDCLASSW(
        style=CS_OWNDC,
        lpfnWndProc=ctypes.cast(user32.DefWindowProcW, p).value,
        hInstance=instance,
        lpszClassName=class_name,
    )
    if not RegisterClassW(ctypes.byref(window_class)):
        raise GLContextError("Cannot register the window class")
    try:
        # no WS_VISIBLE and never ShowWindow'd
        window = CreateWindowExW(
            WS_EX_TOOLWINDOW, class_name, class_name, WS_POPUP, 0, 0, 1, 1,
            None, None, instance, None,
        )  # fmt: skip
        if not window:
            raise GLContextError("Cannot create the hidden window")
        try:
            device = GetDC(window)
            pfd = PIXELFORMATDESCRIPTOR(
                nSize=ctypes.sizeof(PIXELFORMATDESCRIPTOR),
                nVersion=1,
                dwFlags=PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL,
                iPixelType=PFD_TYPE_RGBA,
                cColorBits=32,
                cAlphaBits=8,
                cDepthBits=24,
            )
            pixel_format = ChoosePixelFormat(device, ctypes.byref(pfd))
            if not pixel_format or not SetPixelFormat(
                device, pixel_format, ctypes.byref(pfd)
            ):
                raise GLContextError("Cannot set an OpenGL pixel format")
            context = wglCreateContext(device)
            if not context:
                raise GLContextError("Cannot create the WGL context")
            try:
                if not wglMakeCurrent(device, context):
                    raise GLContextError("Cannot make the WGL context current")
                try:
                    yield
                finally:
                    wglMakeCurrent(None, None)
            finally:
                wglDeleteContext(context)
                ReleaseDC(window, device)
        finally:
            DestroyWindow(window)
    finally:
        UnregisterClassW(class_name, instance)


@contextmanager
def _cgl_context() -> Iterator[None]:
    # CGL contexts need no drawable and no NSApplication, so no dock icon either
    kCGLPFAColorSize = 8
    kCGLPFAAlphaSize = 11
    kCGLPFADepthSize = 12

    cgl = ctypes.CDLL(PLATFORM.CGL._name)
    p = ctypes.c_void_p
    c_int = ctypes.c_int
    CGLChoosePixelFormat = _fn(
        cgl,
        "CGLChoosePixelFormat",
        c_int,
        ctypes.POINTER(c_int),
        ctypes.POINTER(p),
        ctypes.POINTER(c_int),
    )
    CGLDestroyPixelFormat = _fn(cgl, "CGLDestroyPixelFormat", c_int, p)
    CGLCreateContext = _fn(cgl, "CGLCreateContext", c_int, p, p, ctypes.POINTER(p))
    CGLDestroyContext = _fn(cgl, "CGLDestroyContext", c_int, p)
    CGLSetCurrentContext = _fn(cgl, "CGLSetCurrentContext", c_int, p)

    pixel_format = p()
    count = ctypes.c_int()
    error = CGLChoosePixelFormat(
        _attribs({kCGLPFAColorSize: 24, kCGLPFAAlphaSize: 8, kCGLPFADepthSize: 24}),
        ctypes.byref(pixel_format),
        ctypes.byref(count),
    )
    if error or not pixel_format:
        raise GLContextError(f"Cannot choose a CGL pixel format (error {error})")
    context = p()
    error = CGLCreateContext(pixel_format, None, ctypes.byref(context))
    CGLDestroyPixelFormat(pixel_format)
    if error or not context:
        raise GLContextError(f"Cannot create the CGL context (error {error})")
    try:
        if CGLSetCurrentContext(context):
            raise GLContextError("Cannot make the CGL context current")
        try:
            yield
        finally:
            CGLSetCurrentContext(None)
    finally:
        CGLDestroyContext(context)
