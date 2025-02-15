
# Configuring postfix to relay email through Zoho Mail

![](./img/1_VStGP97_hZc0yr6_upQ7Tg.png)

This has taken me quite some time to figure out.

First of all you need the Zoho email address you want to use when relaying emails through Zoho.

It has to be one of the email addresses you configured by using Zoho control panel. In my case I created one to use only to relay email.

Let’s say that this email address is application@example.com. It will have a password as well, say applicationpassword.

When configuring postfix, you edit many files. Let’s see them one by one.

## Generic

The file /etc/postfix/generic maps local users to email addresses.

If email is sent to a local user such root, the address will be replaced with the one you specify.

In my case I have a single line like:

root application@example.com

After editing this file remember to use the command:

postmap generic

## Password

The file /etc/postfix/password contains the passwords postfix has to use to connect to the smtp server.

It’s content will be something like:

smtp.zoho.com:587 application@example.com:applicationpassword

You need to do postmap password.

## tls_policy

The file /etc/postfix/tls_policy contains the policies to be used when sending encrypted emails by using the TLS protocol, the one I’m using in this case.

The file contains just this line:

smtp.zoho.com:587 encrypt

By doing so we force the use of TLS every time we send an email.

You need to do postmap tls_policy.

## smtp_header_checks

The file /etc/postfix/smtp_header_checks contains rules to be used to rewrite the headers of the emails about to be sent.

This is the most important file in our case.

It rewrites the sender so that it always matches our Zoho account, application@example.com.

No more ‘Relaying disallowed’ errors!

This is its content:

1.  /^From:.\*/ REPLACE From: LOCALHOST System <application@emanuelesantanche.com>;

No need for postmap here.

You need to install the package postfix-pcre otherwise no rewriting will happen.

1.  **apt-get install** postfix-pcre

## Main.cf

This is the main configuration file postfix uses.

Replace yourhostname with the hostname of your server, the one where postfix is installed on and that is sending emails through Zoho.

```ini
# TLS parameters
smtp_tls_policy_maps = hash:/etc/postfix/tls_policy
smtpd_tls_cert_file=/etc/ssl/certs/ssl-cert-snakeoil.pem
smtpd_tls_key_file=/etc/ssl/private/ssl-cert-snakeoil.key
smtpd_use_tls=yes
smtpd_tls_session_cache_database = btree:${data_directory}/smtpd_scache
smtp_tls_session_cache_database = btree:${data_directory}/smtp_scache
smtp_header_checks = pcre:/etc/postfix/smtp_header_checks
myhostname = yourhostname
alias_maps = hash:/etc/aliases
alias_database = hash:/etc/aliases
mydestination = yourhostname, localhost.com, localhost
relayhost = smtp.zoho.com:587
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = hash:/etc/postfix/password
smtp_sasl_security_options =
smtp_generic_maps = hash:/etc/postfix/generic

```

## master.cf

In the file /etc/postfix/master.cf I uncommented this line:

```ini
smtps inet n — — — — smtpd
```


## References

* https://medium.com/@esantanche/configuring-postfix-to-relay-email-through-zoho-mail-890b54d5c445
* https://www.reddit.com/r/selfhosted/comments/7tt4go/postfix_not_working_with_zoho_authentication/
* 