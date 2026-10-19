// Application entry point (C++ host). Mirrors main.py, so both hosts run the same qml/ tree:
//
// - registers every font embedded from assets/fonts (and any in a fonts/ folder next to the
//   executable, for fonts added after the build) and logs the family names Qt reports;
// - installs i18n/app_<locale>.qm for APP_LANG or the system locale;
// - loads the App module's Main (compiled into the binary by cmake/S2qQml.cmake);
// - exits non-zero when QML fails to load.
//
// Environment:
//   APP_LOG=debug              more logging
//   APP_LANG=tr                UI language (default: system locale)
//   QT_QUICK_BACKEND=software  GPU-less rendering (the default for the embedded-sw profile)
//   APP_GRAB=out.png           render one frame to a PNG and exit (checks; see build_cpp.py)
//     APP_GRAB_SIZE=1920x1080  window size in logical px (default: the root's own size)
//     APP_GRAB_WAIT_MS=500     settle time before the grab
//     QT_SCALE_FACTOR=2        device pixel ratio of the grab

#include "s2q_qml_plugins.h"

#include <QCoreApplication>
#include <QDir>
#include <QDirIterator>
#include <QFontDatabase>
#include <QGuiApplication>
#include <QImage>
#include <QLocale>
#include <QLoggingCategory>
#include <QQmlApplicationEngine>
#include <QQmlError>
#include <QQuickWindow>
#include <QSGRendererInterface>
#include <QTimer>
#include <QTranslator>

Q_LOGGING_CATEGORY(lcApp, "app", QtInfoMsg)

namespace {

int loadFonts(const QStringList &folders)
{
    int count = 0;
    for (const QString &folder : folders) {
        QDirIterator it(folder, {"*.ttf", "*.otf", "*.ttc", "*.TTF", "*.OTF"}, QDir::Files);
        while (it.hasNext()) {
            const QString path = it.next();
            const int id = QFontDatabase::addApplicationFont(path);
            if (id == -1) {
                qCWarning(lcApp) << "font not loaded:" << path;
                continue;
            }
            ++count;
            qCDebug(lcApp) << "font" << path << "->" << QFontDatabase::applicationFontFamilies(id);
        }
    }
    return count;
}

void installTranslation(QGuiApplication &app)
{
    const QByteArray lang = qgetenv("APP_LANG");
    const QLocale locale = lang.isEmpty() ? QLocale::system() : QLocale(QString::fromLatin1(lang));
    auto *translator = new QTranslator(&app);
    if (translator->load(locale, "app", "_", ":/qt/i18n")) {
        QCoreApplication::installTranslator(translator);
        qCDebug(lcApp) << "translation" << translator->filePath() << "loaded";
    } else {
        delete translator;
    }
}

} // namespace

int main(int argc, char *argv[])
{
    if (qgetenv("APP_LOG").toLower() == "debug")
        QLoggingCategory::setFilterRules("app.debug=true");
    if (QStringLiteral(APP_PROFILE) == "embedded-sw" && qEnvironmentVariableIsEmpty("QT_QUICK_BACKEND"))
        QQuickWindow::setGraphicsApi(QSGRendererInterface::Software);

    QGuiApplication app(argc, argv);
    QCoreApplication::setOrganizationName(APP_ORG);
    QCoreApplication::setApplicationName(APP_NAME);

    const QString localFonts = QCoreApplication::applicationDirPath() + "/fonts";
    loadFonts({":/qt/assets/fonts", localFonts});
    installTranslation(app);

    QQmlApplicationEngine engine;
    QStringList warnings;
    QObject::connect(&engine, &QQmlApplicationEngine::warnings, &app, [&warnings](const QList<QQmlError> &ws) {
        for (const QQmlError &w : ws)
            warnings << w.toString();
    });
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app,
                     [] { QCoreApplication::exit(1); }, Qt::QueuedConnection);
    engine.loadFromModule("App", "Main");
    if (engine.rootObjects().isEmpty()) {
        qCCritical(lcApp) << "QML failed to load:" << warnings;
        return 1;
    }

    const QString grabPath = qEnvironmentVariable("APP_GRAB");
    if (!grabPath.isEmpty()) {
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().constFirst());
        if (!window) {
            qCCritical(lcApp) << "root object is not a Window";
            return 2;
        }
        const QStringList size = qEnvironmentVariable("APP_GRAB_SIZE").split('x');
        if (size.size() == 2) {
            window->resize(size[0].toInt(), size[1].toInt());
            window->setWidth(size[0].toInt());
            window->setHeight(size[1].toInt());
        }
        window->show();
        const int wait = qEnvironmentVariableIsSet("APP_GRAB_WAIT_MS") ? qEnvironmentVariableIntValue("APP_GRAB_WAIT_MS") : 500;
        QTimer::singleShot(wait, &app, [&app, window, grabPath, &warnings] {
            const QImage img = window->grabWindow();
            const bool ok = !img.isNull() && img.save(grabPath);
            for (const QString &w : std::as_const(warnings))
                fprintf(stderr, "[qml] %s\n", qPrintable(w));
            fprintf(stdout, "grabbed %s (%dx%d, %s, %d warnings)\n", qPrintable(grabPath), img.width(), img.height(),
                    qPrintable(QQuickWindow::sceneGraphBackend().isEmpty() ? QStringLiteral("rhi")
                                                                            : QQuickWindow::sceneGraphBackend()),
                    int(warnings.size()));
            app.exit(ok ? 0 : 2);
        });
    }
    return app.exec();
}
