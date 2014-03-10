*** Settings ***
Resource   saucelabs.robot

Test Setup        Open SauceLabs test browser
Test Teardown     Run keywords  Report test status   Close All Browsers

*** Test Cases ***

Scenario: Test Dashboard view
     When I go to  ${APP_URL}/login_form
     Then Page Should Contain  Login form
     Input Text     login       ${USERNAME}
     Input Text     password    ${PASSWORD}
     Click Button   Login
     Then Page Should Contain  Active projects

*** Keywords ***

I go to
    [Arguments]  ${location}
    Go to  ${location}
