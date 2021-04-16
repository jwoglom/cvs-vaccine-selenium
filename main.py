#!/usr/bin/env python3
import os, time

from selenium.webdriver import Firefox, FirefoxProfile, Chrome
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By
from fake_useragent import UserAgent
from zipfile import ZipFile

import requests
import json
import random
from urllib.parse import urljoin

import time
import os, os.path

FIRST_STEP = "https://www.cvs.com/vaccine/intake/store/cvd-schedule?icid=coronavirus-lp-vaccine-sd-statetool"
START_VACCINATION = "I need to start vaccination."
ONE_MEDICAL_CONDITION = "Age 16+ with an eligible medical condition that increases the risk of severe illness from COVID-19"

class ItemNotClickedException(Exception):
    pass

def download_ublock_xpi():
    ublock_xpi = 'ublock.xpi'
    UBLOCK_XPI_URL = 'https://github.com/gorhill/uBlock/releases/download/1.34.1b4/uBlock0_1.34.1b4.firefox.signed.xpi'

    if not os.path.exists(ublock_xpi):
        print("Downloading uBlock extension...")
        with open(ublock_xpi, 'wb') as f:
            f.write(requests.get(UBLOCK_XPI_URL).content)

    return ublock_xpi

def download_ublock_zip():
    ublock_zip = 'ublock.zip'
    UBLOCK_ZIP_URL = 'https://github.com/gorhill/uBlock/releases/download/1.34.1b4/uBlock0_1.34.1b4.chromium.zip'

    if not os.path.exists(ublock_zip):
        print("Downloading uBlock extension...")
        with open(ublock_zip, 'wb') as f:
            f.write(requests.get(UBLOCK_ZIP_URL).content)

    path = os.path.join(os.getcwd(), 'ublock-chrome')
    if not os.path.exists(path):
        with ZipFile(ublock_zip, 'r') as z:
            z.extractall(path)
    
    return os.path.join(path, 'uBlock0.chromium')


def init_driver(browser):
    userAgent = UserAgent().random
    if browser == 'firefox':
        opts = FirefoxOptions()
        opts.headless = False

        fp = FirefoxProfile()
        fp.set_preference("general.useragent.override", userAgent)

        driver = Firefox(options=opts, firefox_profile=fp)
        print("Installing uBlock Origin...")
        driver.install_addon(os.path.join(os.getcwd(), download_ublock_xpi()), temporary=True)

        return driver
    elif browser == 'chrome':
        opts = ChromeOptions()
        opts.headless = False
        opts.add_argument('user-agent=%s' % userAgent)
        opts.add_argument('load-extension=%s' % download_ublock_zip())

        return Chrome(options=opts)
    else:
       raise Exception('Choose firefox or chrome')

def check_appointments(state, address, eligibility_age=None, eligibility_group=None, browser='firefox'):
    driver = init_driver(browser)
     
    def wait(sel):
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))

    def click(sel):
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
        item = driver.find_element_by_css_selector(sel)
        if item:
            item.click()
            return True
        raise ItemNotClickedException()
    
    def get_questions(sec):
        wait(".%s .form-group" % sec)
        ret = driver.execute_script("""
var ret = {};
document.querySelectorAll(".%s .form-group").forEach(question => {
  var label = question.querySelector("label").innerText.trim();
  ret[label] = [];
  question.querySelectorAll(".radioBtn-control").forEach(item => {
    ret[label].push(item.innerText.trim());
  });
  if (question.querySelector(".answer-free-input")) ret[label] = "";
  if (question.querySelector(".checkbox-control")) ret[label] = false;
});
return ret
        """ % sec)
        print("%s: %s" % (sec, ret))
        return ret

    def set_questions(sec, inp):
        wait(".%s .form-group" % sec)
        driver.execute_script("""
var input = %s;
document.querySelectorAll(".%s .form-group").forEach(question => {
  var label = question.querySelector("label").innerText.trim();
  if (!!input[label]) {
    question.querySelectorAll(".radioBtn-control").forEach(item => {
      if (input[label] == item.innerText.trim()) {
        item.querySelector("input").click();
      }
    });
    var inp = question.querySelector(".answer-free-input");
    if (!!inp) {
        // This does not work on its own due to angular issues
        inp.value = parseInt(input[label].trim());
    }
    var chk = question.querySelector(".checkbox-control");
    if (!!chk && input[label]) {
        chk.querySelector("input").click();
        chk.querySelector("input").checked = true;
    }
  }
});
        """ % (json.dumps(inp), sec))
    
    def set_state(state):
        wait("#jurisdiction > option")
        Select(driver.find_element_by_id("jurisdiction")).select_by_visible_text(state)

    def set_age(age):
        wait(".eligbility-info input.answer-free-input")
        driver.find_element_by_css_selector(".eligbility-info input.answer-free-input").send_keys(age)

    def set_address(address):
        wait("#address")
        driver.find_element_by_id("address").send_keys(address)
        time.sleep(0.5)
    
    def search_locations():
        wait(".store-locator-form button")
        click(".store-locator-form button")
    
    def next_page():
        time.sleep(random.random() * 1.5)
        click(".footer-content-wrapper button")
        time.sleep(random.random() * 1.5)

    try:
        driver.get(FIRST_STEP)

        # Never had COVID
        wait(".questions-info-sec .form-group")
        
        questions = {}
        for q in get_questions("questions-info-sec"):
            questions[q] = 'No'
        
        set_questions("questions-info-sec", questions)

        next_page()

        # Need first dose
        wait(".covid-dose-sel-sec .form-group")
        questions = {}
        for q in get_questions("covid-dose-sel-sec"):
            questions[q] = START_VACCINATION
            break
        
        set_questions("covid-dose-sel-sec", questions)

        next_page()

        set_state(state)

        next_page()

        if state == 'Massachusetts':
            questions = {}
            for q in get_questions("eligbility-info"):
                if "What is your age" in q and eligibility_age:
                    questions[q] = str(eligibility_age)
                    set_age(str(eligibility_age))
                elif "Which group" in q and eligibility_group:
                    questions[q] = str(eligibility_group)
                else:
                    questions[q] = True
            set_questions("eligbility-info", questions)


        print("Manually select or verify eligibility criteria and click next when done")

        WebDriverWait(driver, 99999).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".how-to-container")))

        print("Continuing...")

        next_page()

        set_address(address)
        #search_locations()


        

        time.sleep(999999)


    finally:
        driver.quit()


if __name__ == '__main__':
    check_appointments(
        state=input('State: '),
        address=input('Address: '),
        eligibility_age=int(input('Age: ')),
        eligibility_group=ONE_MEDICAL_CONDITION,
        browser='firefox'
    )