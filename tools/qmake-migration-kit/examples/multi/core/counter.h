#pragma once
#include <QtCore/QObject>

class Counter : public QObject {
    Q_OBJECT
public:
    void increment();
    int value() const { return m_value; }
signals:
    void changed(int value);
private:
    int m_value = 0;
};
