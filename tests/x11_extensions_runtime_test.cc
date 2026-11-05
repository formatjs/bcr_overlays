#include <cstdio>
#include <string>

#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/XTest.h>
#include <X11/extensions/Xcomposite.h>
#include <X11/extensions/Xdamage.h>
#include <X11/extensions/Xfixes.h>
#include <X11/extensions/Xrandr.h>
#include <X11/extensions/Xrender.h>

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

int CheckX11Extensions(const std::string& display_name) {
  Display* display = XOpenDisplay(display_name.c_str());
  CHECK_CASE(display);
  int event_base = 0;
  int error_base = 0;
  int major = 0;
  int minor = 0;
  CHECK_CASE(XCompositeQueryExtension(display, &event_base, &error_base));
  CHECK_CASE(XCompositeQueryVersion(display, &major, &minor));
  CHECK_CASE(major > 0 || minor >= 2);
  CHECK_CASE(XFixesQueryExtension(display, &event_base, &error_base));
  int damage_base = 0;
  CHECK_CASE(XDamageQueryExtension(display, &damage_base, &error_base));
  CHECK_CASE(XRRQueryVersion(display, &major, &minor));
  CHECK_CASE(XRenderQueryVersion(display, &major, &minor));
  CHECK_CASE(
      XTestQueryExtension(display, &event_base, &error_base, &major, &minor));

  const int screen = DefaultScreen(display);
  const Window root = RootWindow(display, screen);
  const Window window =
      XCreateSimpleWindow(display, root, 0, 0, 64, 48, 0, 0, 0);
  XCompositeRedirectWindow(display, window, CompositeRedirectAutomatic);
  XMapWindow(display, window);
  XSync(display, False);
  const Pixmap pixmap = XCompositeNameWindowPixmap(display, window);
  CHECK_CASE(pixmap != None);
  Window drawable_root = None;
  int x = 0;
  int y = 0;
  unsigned int width = 0;
  unsigned int height = 0;
  unsigned int border = 0;
  unsigned int depth = 0;
  CHECK_CASE(XGetGeometry(display, pixmap, &drawable_root, &x, &y, &width,
                          &height, &border, &depth));
  CHECK_CASE(width == 64 && height == 48);
  const Damage damage = XDamageCreate(display, window, XDamageReportNonEmpty);
  Visual* visual = DefaultVisual(display, screen);
  XRenderPictFormat* format = XRenderFindVisualFormat(display, visual);
  CHECK_CASE(format);
  const Picture picture =
      XRenderCreatePicture(display, window, format, 0, nullptr);
  XRenderColor red{0xffff, 0, 0, 0xffff};
  XRenderFillRectangle(display, PictOpSrc, picture, &red, 0, 0, 64, 48);
  XSync(display, False);
  XImage* image = XGetImage(display, pixmap, 0, 0, 1, 1, AllPlanes, ZPixmap);
  CHECK_CASE(image);
  const unsigned long pixel = XGetPixel(image, 0, 0);
  CHECK_CASE((pixel & visual->red_mask) != 0);
  CHECK_CASE((pixel & (visual->green_mask | visual->blue_mask)) == 0);
  XDestroyImage(image);
  bool damaged = false;
  while (XPending(display)) {
    XEvent event;
    XNextEvent(display, &event);
    if (event.type == damage_base + XDamageNotify) {
      const auto& notification =
          reinterpret_cast<const XDamageNotifyEvent&>(event);
      damaged |= notification.drawable == window &&
                 notification.area.width > 0 && notification.area.height > 0;
    }
  }
  CHECK_CASE(damaged);

  XRectangle rectangle{2, 3, 10, 20};
  const XserverRegion region = XFixesCreateRegion(display, &rectangle, 1);
  int count = 0;
  XRectangle* rectangles = XFixesFetchRegion(display, region, &count);
  CHECK_CASE(rectangles && count == 1);
  CHECK_CASE(rectangles[0].x == 2 && rectangles[0].y == 3 &&
             rectangles[0].width == 10 && rectangles[0].height == 20);
  XFree(rectangles);
  XFixesDestroyRegion(display, region);
  CHECK_CASE(XTestFakeMotionEvent(display, screen, 13, 17, CurrentTime));
  XSync(display, False);
  Window child = None;
  int root_x = 0;
  int root_y = 0;
  unsigned int mask = 0;
  CHECK_CASE(XQueryPointer(display, root, &drawable_root, &child, &root_x,
                           &root_y, &x, &y, &mask));
  CHECK_CASE(root_x == 13 && root_y == 17);
  XRRScreenResources* resources = XRRGetScreenResourcesCurrent(display, root);
  CHECK_CASE(resources && resources->ncrtc > 0 && resources->nmode > 0);
  XRRFreeScreenResources(resources);
  XRenderFreePicture(display, picture);
  XDamageDestroy(display, damage);
  XFreePixmap(display, pixmap);
  XCompositeUnredirectWindow(display, window, CompositeRedirectAutomatic);
  XDestroyWindow(display, window);
  XCloseDisplay(display);
  std::puts(
      "Native X11 extensions: composite/render pixels, damage, regions, "
      "pointer and RandR passed");
  return 0;
}
