#include <boost/test/unit_test.hpp>
#include <concepts>

BOOST_AUTO_TEST_SUITE(Project_Test_Suite)

BOOST_AUTO_TEST_SUITE(Module_Test_Suite)

BOOST_AUTO_TEST_CASE(DummyTest_Passes) {
  BOOST_CHECK_EQUAL(1, 1);
  BOOST_CHECK(true);
}

BOOST_AUTO_TEST_CASE(test_move) {
  static_assert(std::movable<class_name<int, int>>, "class is not movable");
  BOOST_CHECK(true);
}

BOOST_AUTO_TEST_CASE(test_copy) {
  static_assert(std::copyable<class_name<int, int>>, "class is not movable");
  BOOST_CHECK(true);
}

BOOST_AUTO_TEST_SUITE_END()

BOOST_AUTO_TEST_SUITE_END()