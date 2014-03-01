*** Settings ***

Variables  penelope/core/tests/robot/variables.py

Library  Selenium2Library  timeout=${SELENIUM_TIMEOUT}  implicit_wait=${SELENIUM_IMPLICIT_WAIT}

Suite Setup  Suite Setup
Suite Teardown  Suite Teardown

*** Test Cases ***

Scenario: Test Dashboard view
     When I go to  ${APP_URL}/login_form
     Then Page Should Contain  Login form
     Input Text     login       ${USERNAME}
     Input Text     password    ${PASSWORD}
     Click Button   Login
     Then Page Should Contain  Active projects

*** Keywords ***

Suite Setup
  Open browser  ${APP_URL}  browser=${BROWSER}  remote_url=${REMOTE_URL}  desired_capabilities=${DESIRED_CAPABILITIES}

Suite Teardown
  Close All Browsers

I go to
    [Arguments]  ${location}
    Go to  ${location}
