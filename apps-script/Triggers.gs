function installTriggers() {
  uninstallTriggers();
  ScriptApp.newTrigger('sendMonthlyReport').timeBased().onMonthDay(CONFIG.sendDay).atHour(CONFIG.sendHour).create();
  console.log('Trigger installiert: sendMonthlyReport am ' + CONFIG.sendDay + '. um ' + CONFIG.sendHour + ' Uhr');
}
function uninstallTriggers() {
  ScriptApp.getProjectTriggers().forEach(t => { if (t.getHandlerFunction() === 'sendMonthlyReport') ScriptApp.deleteTrigger(t); });
}
function listTriggers() {
  ScriptApp.getProjectTriggers().forEach(t => console.log(t.getHandlerFunction() + ' / ' + t.getEventType()));
}
