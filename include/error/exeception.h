//
// Created by przemek on 18.03.2020.
//

#ifndef TEMPLATE_EXECEPTION_H
#define TEMPLATE_EXECEPTION_H

#include <iostream>
#include <stdexcept>

namespace temp_project {
    namespace error {
        class exception : public std::runtime_error {
        public:
            explicit exception(const std::string &desc) : runtime_error(desc) {}
        };

        class runtime_exception : public exception{
        public:
            explicit runtime_exception(const std::string &desc) : exception(desc) {}
        };
    }
}

#endif //TEMPLATE_EXECEPTION_H
