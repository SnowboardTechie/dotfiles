ObjC.import('Foundation');

function clean(value, limit) {
  if (value === undefined || value === null) return null;
  const text = String(value).replace(/\u0000/g, '').replace(/\s+/g, ' ').trim();
  return text ? text.slice(0, limit) : null;
}

function run(argv) {
  const since = new Date(argv[0]);
  const maximum = Number(argv[1] || 40);
  const Mail = Application('Mail');
  const rows = [];

  for (const account of Mail.accounts()) {
    let enabled = true;
    try { enabled = account.enabled(); } catch (_) {}
    if (!enabled) continue;
    const mailboxes = account.mailboxes();
    const inbox = mailboxes.find(box => String(box.name()).toUpperCase() === 'INBOX');
    if (!inbox) continue;
    for (const message of inbox.messages()) {
      const received = message.dateReceived();
      const unread = !message.readStatus();
      if (received >= since || unread) {
        rows.push({
          source: 'apple_mail',
          account: clean(account.name(), 200),
          messageId: clean(message.messageId(), 500),
          sender: clean(message.sender(), 500),
          subject: clean(message.subject(), 500),
          date: received.toISOString(),
          unread: unread,
          snippet: clean(message.content(), 600)
        });
      }
    }
  }

  rows.sort((a, b) => b.date.localeCompare(a.date));
  return JSON.stringify(rows.slice(0, maximum));
}
