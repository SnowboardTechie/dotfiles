ObjC.import('Foundation');

function clean(value, limit) {
  if (value === undefined || value === null) return null;
  const text = String(value).replace(/\u0000/g, '').replace(/\s+/g, ' ').trim();
  return text ? text.slice(0, limit) : null;
}

function run(argv) {
  const accountName = 'Google';
  const since = new Date(argv[0]);
  const maximum = Number(argv[1] || 30);
  const Mail = Application('Mail');
  const account = Mail.accounts.byName(accountName);
  const inbox = account.mailboxes.byName('INBOX');
  const messages = inbox.messages();
  const rows = [];

  for (let index = 0; index < messages.length && rows.length < maximum; index++) {
    const message = messages[index];
    const received = message.dateReceived();
    const unread = !message.readStatus();
    if (received >= since || unread) {
      rows.push({
        source: 'apple_mail',
        messageId: clean(message.messageId(), 500),
        sender: clean(message.sender(), 500),
        subject: clean(message.subject(), 500),
        date: received.toISOString(),
        unread: unread,
        snippet: clean(message.content(), 900)
      });
    }
  }

  rows.sort((a, b) => b.date.localeCompare(a.date));
  return JSON.stringify(rows);
}
