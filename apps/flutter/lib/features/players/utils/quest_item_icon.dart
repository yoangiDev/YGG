/// Role Quest item icon URLs (Data Dragon + Community Dragon fallbacks).
library;

const _cdBase =
    'https://raw.communitydragon.org/latest/game/assets/items/icons2d';

/// Community Dragon overrides for internal role-quest item ids.
const questItemIconOverrides = <int, String>{
  1206: '$_cdBase/rolequest_midreward_complete.png',
  1208: '$_cdBase/rolequest_supportreward_empty.png',
  1209: '$_cdBase/rolequest_junglereward_inprogress.png',
  1220: '$_cdBase/rolequest_topreward2_complete.png',
  1221: '$_cdBase/rolequest_topreward1_complete.png',
};

String? questItemIconUrl(int itemId, String? ddragonVersion) {
  if (itemId <= 0) return null;
  final override = questItemIconOverrides[itemId];
  if (override != null) return override;
  if (ddragonVersion == null) return null;
  return 'https://ddragon.leagueoflegends.com/cdn/$ddragonVersion/img/item/$itemId.png';
}
