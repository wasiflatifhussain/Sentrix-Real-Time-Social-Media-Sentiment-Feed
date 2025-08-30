tutorial: https://www.youtube.com/watch?v=x9boO9x3TDA&ab_channel=Andy%27sTechTutorials

repo: https://github.com/reddit-archive/reddit/wiki/OAuth2-Quick-Start-Example

postman api calls (clone and import to Postman): https://github.com/AndyUGA/Reddit_API_Postman_Collection_and_Environment_Variables

steps:
- use POST access_token on Postman to get access token
- use GET reddit-about-me for info about user (your account)
- now make any API call from: https://www.reddit.com/dev/api/

- note: the postman token expires every 1 hour - so request renewal and use it as bearer <token> to get api request succwaa