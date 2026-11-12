#include <QtCore/QCoreApplication>
#include <QLinkedList>
#include <QRegExp>
#include <QTextCodec>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    QRegExp rx(QStringLiteral("(\\d+)"));
    const int pos = rx.indexIn(QStringLiteral("abc 42"));
    QTextCodec *codec = QTextCodec::codecForName("UTF-8");
    QLinkedList<int> list;
    list << 1 << 2;
    return pos == 4 && codec && list.size() == 2 ? 0 : 1;
}
