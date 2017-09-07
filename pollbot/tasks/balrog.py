from pollbot.exceptions import TaskError
from pollbot.utils import Channel, get_version_channel, build_version_id
from . import get_session, build_task_response, heartbeat_factory


async def get_build_info(release_mapping):
    release_url = 'https://aus-api.mozilla.org/api/v1/releases/{}'.format(release_mapping)
    with get_session() as session:
            async with session.get(release_url) as resp:
                body = await resp.json()
                platforms = body['platforms']
                linux_x64_platform = [x for x in platforms.keys()
                                      if 'linux' in x.lower() and 'x86_64' in x.lower()]
                if not linux_x64_platform:
                    raise TaskError('Linux x86_64 platform not found in {}'.format(
                        list(platforms.keys())))

                platform_info = platforms[linux_x64_platform.pop()]['locales']['en-US']
                buildID = platform_info['buildID']
                appVersion = platform_info['appVersion']

                return buildID, appVersion


async def balrog_rules(product, version):
    channel = get_version_channel(version)
    if channel is Channel.NIGHTLY:
        # In that case the rule doesn't change, so we grab the buildID.

        # There are case were Nightly is deactivated, in that case
        # the mapping is not nightly-latest anymore
        url = 'https://aus-api.mozilla.org/api/v1/rules/firefox-nightly'
        with get_session() as session:
            async with session.get(url) as resp:
                rule = await resp.json()
                status = rule['mapping'] == 'Firefox-mozilla-central-nightly-latest'

                buildID, appVersion = await get_build_info(rule['mapping'])

                exists_message = (
                    'Balrog rule is configured for the latest Nightly {} build ({}) '
                    'with an update rate of {}%').format(
                        appVersion, buildID, rule['backgroundRate'])
                missing_message = (
                    'Balrog rule is configured for {} {} ({}) '
                    'with an update rate of {}%').format(
                        rule['mapping'], appVersion, buildID, rule['backgroundRate'])

                return build_task_response(status, url, exists_message, missing_message)

    elif channel is Channel.BETA:
        url = 'https://aus-api.mozilla.org/api/v1/rules/firefox-beta'
    else:
        url = 'https://aus-api.mozilla.org/api/v1/rules/firefox-release'
    # elif channel is Channel.ESR: XXX: Fix ESR rule URL
    #     url = 'https://aus-api.mozilla.org/api/v1/rules/firefox-esr'

    with get_session() as session:
        async with session.get(url) as resp:
            rule = await resp.json()
            buildID, appVersion = await get_build_info(rule['mapping'])
            status = build_version_id(appVersion) >= build_version_id(version)
            exists_message = (
                'Balrog rule has been updated for {} ({}) with an update rate of {}%'
            ).format(rule['mapping'], buildID, rule['backgroundRate'])
            missing_message = (
                'Balrog rule is set for {} ({}) with an update rate of {}%'
            ).format(rule['mapping'], buildID, rule['backgroundRate'])
            return build_task_response(status, url, exists_message, missing_message)


heartbeat = heartbeat_factory('https://aus-api.mozilla.org/__heartbeat__')
