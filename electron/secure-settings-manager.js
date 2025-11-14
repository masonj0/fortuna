// electron/secure-settings-manager.js
const { app } = require('electron');
const fs = require('fs');
const path = require('path');

const SETTINGS_FILE = path.join(app.getPath('userData'), 'settings.json');

class SecureSettingsManager {
 constructor() {
 this.settings = this.loadSettings();
 }

 loadSettings() {
 try {
 if (fs.existsSync(SETTINGS_FILE)) {
 const data = fs.readFileSync(SETTINGS_FILE, 'utf-8');
 return JSON.parse(data);
 }
 } catch (error) {
 console.error('Error loading settings:', error);
 }
 return {};
 }

 saveSettings() {
 try {
 fs.writeFileSync(SETTINGS_FILE, JSON.stringify(this.settings, null, 2));
 } catch (error) {
 console.error('Error saving settings:', error);
 }
 }

 getApiKey() {
 return this.settings.apiKey || null;
 }

 saveApiKey(apiKey) {
 this.settings.apiKey = apiKey;
 this.saveSettings();
 return { success: true };
 }

 getBetfairCredentials() {
 return this.settings.betfair || null;
 }

 saveBetfairCredentials(credentials) {
 this.settings.betfair = credentials;
 this.saveSettings();
 return { success: true };
 }
}

module.exports = new SecureSettingsManager();
