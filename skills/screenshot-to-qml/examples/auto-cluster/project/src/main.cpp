// Application entry point (C++ host, Qt 5.15). Same contract as the Qt 6 host:
//
// - registers every font embedded from assets/fonts (and any in a fonts/ folder next to the
//   executable, for fonts added after the build) and logs the family names Qt reports;
// - installs i18n/app_<locale>.qm for APP_LANG or the system locale;
// - loads qrc:/qml/App/Main.qml with qrc:/qml as the import path (cmake/S2qQml5.cmake);
// - exits non-zero when QML fails to load.
//
// Environment:
//   APP_LOG=debug              more logging
//   APP_LANG=tr                UI language (default: system locale)
//   QT_QUICK_BACKEND=software  GPU-less rendering (the default for the embedded-sw profile)
//   APP_GRAB=out.png           render one frame to a PNG and exit (checks; see build_cpp.py)
//     APP_GRAB_SIZE=1920x720   window size in logical px (default: the root's own size)
//     APP_GRAB_WAIT_MS=500     settle time before the grab
//     QT_SCALE_FACTOR=2        device pixel ratio of the grab

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
#include <QUrl>

#include <cstdio>
#include <utility>

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
    if (translator->load(locale, "app", "_", ":/i18n")) {
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
    QCoreApplication::setAttribute(Qt::AA_EnableHighDpiScaling);
    // Qt 5 rounds scale factors by default (1.25 -> 1); Qt 6 and the check loop pass them through
    QGuiApplication::setHighDpiScaleFactorRoundingPolicy(Qt::HighDpiScaleFactorRoundingPolicy::PassThrough);
    if (QStringLiteral(APP_PROFILE) == "embedded-sw" && qEnvironmentVariableIsEmpty("QT_QUICK_BACKEND"))
        QQuickWindow::setSceneGraphBackend(QSGRendererInterface::Software);

    QGuiApplication app(argc, argv);
    QCoreApplication::setOrganizationName(APP_ORG);
    QCoreApplication::setApplicationName(APP_NAME);

    const QString localFonts = QCoreApplication::applicationDirPath() + "/fonts";
    loadFonts({":/assets/fonts", localFonts});
    installTranslation(app);

    QQmlApplicationEngine engine;
    QStringList warnings;
    QObject::connect(&engine, &QQmlApplicationEngine::warnings, &app, [&warnings](const QList<QQmlError> &ws) {
        for (const QQmlError &w : ws)
            warnings << w.toString();
    });
    const QUrl mainUrl(QStringLiteral("qrc:/qml/App/Main.qml"));
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreated, &app,
                     [mainUrl](QObject *obj, const QUrl &url) {
                         if (!obj && url == mainUrl)
                             QCoreApplication::exit(1);
                     }, Qt::QueuedConnection);
    engine.addImportPath(QStringLiteral("qrc:/qml"));
    engine.load(mainUrl);
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
            const QString backend = QQuickWindow::sceneGraphBackend();
            fprintf(stdout, "grabbed %s (%dx%d, %s, Qt %s, %d warnings)\n", qPrintable(grabPath), img.width(),
                    img.height(), qPrintable(backend.isEmpty() ? QStringLiteral("opengl") : backend), qVersion(),
                    int(warnings.size()));
            app.exit(ok ? 0 : 2);
        });
    }
    return app.exec();
}
