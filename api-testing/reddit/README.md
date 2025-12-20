# Reddit API with Postman

## Follow:

- Yt Tutorial: https://www.youtube.com/watch?v=x9boO9x3TDA&ab_channel=Andy%27sTechTutorials
- Make Reddit account
- A Reddit developer app (script type) → [Create one here](https://www.reddit.com/prefs/apps)
- Postman installed
- [Reddit Postman collection & environment](https://github.com/AndyUGA/Reddit_API_Postman_Collection_and_Environment_Variables) cloned/imported

## Environment Variables

Set these variables in **Postman environment** (or in an `.env.local` file if running locally):

```bash
CLIENT_ID=<reddit app's personal use script>
CLIENT_SECRET=<reddit app's secret>
REDDIT_USERNAME=<your reddit username>
REDDIT_PASSWORD=<your reddit password>
```

## Steps:

- Use POST access_token on Postman to get access token [follow the Youtube tutorial]
  POST -> https://www.reddit.com/api/v1/access_token
  Authorization: Basic Auth -> Username = Reddit App's Personal User Script
  -> Password = Reddit App's Secret
  Body: use x-www-form-urlencoded and put these fields ->
  grant_type: password
  username: Your Reddit Username
  password: Your Reddit Password
- Use GET requests similar to those on Postman

- Note: the postman token expires every 1 hour - so request renewal and use it as bearer <token> to get api request success

## Authentication Flow

- This project uses Reddit OAuth2 (script app)
- Access tokens are fetched programmatically at runtime
- Tokens are NOT stored manually and are NOT committed

### Runtime flow:

1. The app reads Reddit credentials from `.env.local`
2. A new access token is requested from:
   https://www.reddit.com/api/v1/access_token
3. The token is automatically injected as:
   Authorization: bearer <token>
4. When the token expires (~1 hour), a new one is requested automatically
