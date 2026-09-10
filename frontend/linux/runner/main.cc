#include "my_application.h"

int main(int argc, char** argv) {
  g_autoptr(MyApplication) app = my_application_new();

  gchar* exec_path = g_canonicalize_filename(argv[0], nullptr);
  if (exec_path != nullptr) {
    gchar* bundle_dir = g_path_get_dirname(exec_path);
    gchar* icon_path = g_build_filename(bundle_dir, "data", "app_icon.png", nullptr);
    g_autoptr(GError) error = nullptr;
    if (!gtk_window_set_default_icon_from_file(icon_path, &error)) {
      g_warning("Unable to load Linux app icon: %s", error->message);
    }
    g_free(icon_path);
    g_free(bundle_dir);
    g_free(exec_path);
  }

  return g_application_run(G_APPLICATION(app), argc, argv);
}
