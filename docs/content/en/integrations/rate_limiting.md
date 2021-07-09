---
title: "Rate Limiting"
description: "Configurable rate limiting on the login page to mitigate brute force attacks"
draft: false
weight: 9
---


DefectDojo has protection against brute force attacks through rate limiting

## Configuration

For further information, please visit the package documentation [Django Ratelimit](https://django-ratelimit.readthedocs.io/en/stable/index.html)

#### Enable Rate Limiting

To enable and configure rate limiting, edit the `dojo/settings/settings.dist.py` file and edit/replace the following information:

    {{< highlight python >}}
    DD_RATE_LIMITER_ENABLED=(bool, True),
    DD_RATE_LIMITER_RATE=(str, '5/m'),
    DD_RATE_LIMITER_BLOCK=(bool, True),
    DD_RATE_LIMITER_ACCOUNT_LOCKOUT=(bool, True),
    {{< /highlight >}}

#### Rate Limit

The frequency at which the request will be limited can be set to 

* seconds - `1s`
* minutes - `5m`
* hours - `100h`
* days - `2400d`

Extended configuration can be found [here](https://django-ratelimit.readthedocs.io/en/stable/rates.html)

#### Block Requests

By default, rate limiting is set to record offenses, but does not actually block requests and enforce the limit.

Setting `DD_RATE_LIMITER_BLOCK` will block all incoming requests at the configured frequncy once that frequency has been exceeded. 

#### Account Lockout 

In the event of a brute force attack, a users credentials could potentially be comprimised. 

In an attempt to circumvent that event, setting `DD_RATE_LIMITER_ACCOUNT_LOCKOUT` will force a user to reset their password upon the next attempted login. 

#### Multi-Process Behavior

When using configurations with multiple uwsgi processes, the rate limiting package uses the default cache that is memory based and local to a process.

#### Extra Configuation 

For further information, please visit the package documentation [Django Ratelimit](https://django-ratelimit.readthedocs.io/en/stable/index.html)
