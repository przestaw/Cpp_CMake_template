#include <project_defines.h>
#include <iostream>
#include <fstream>

using namespace boost::program_options;

/**
 * Params struct for storing runtime params
 */
struct Params {
    bool run = false;
} params;                                               //!< global Params object

/**
 * Function for arguments parsing
 * @param argc arguments count from stdin
 * @param argv arguments array
 */
inline void parseParams(int argc, char *argv[]) {
    try {
        options_description desc{"Options"};
        desc.add_options()
                ("help,h", "Help screen")
                ("input,i", value<std::vector<std::string>>()->multitoken(), "Input file");

        variables_map vm;
        store(parse_command_line(argc, argv, desc), vm);
        notify(vm);

        /* Parse options */
        if (vm.count("help")) {
            std::cout << desc << '\n';
        } else {
            if (vm.count("input") > 0) {
                params.run = true;

            }
        }
    } catch (const boost::program_options::error &ex) {
        std::cerr << ex.what() << " !\n";
    }
}

/**
 * Main function
 * @return 0 on success
 */
int main(int argc, char *argv[]) {
    std::cout << "Hello, World!\n"
              << FBLU("by Stawczyk Przemyslaw")
              << std::endl; //flush stream

    parseParams(argc, argv);
    if (params.run) {
        std::cout << FGRN("RUN\n");
    }
    return 0;
}
