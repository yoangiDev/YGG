class Endpoints {
  Endpoints._();

  static const String baseUrl = 'https://ygg-tfg.onrender.com';

  // Auth
  static const String login = '/auth/login';
  static const String register = '/auth/register';
  static const String me = '/auth/me';
  static const String changeMyPassword = '/auth/me/password';
  static const String updateAvatar     = '/auth/me/avatar';

  // Players
  static const String players = '/players/';
  static String player(int id) => '/players/$id';
  static String refreshPlayer(int id) => '/players/$id/refresh';

  // Matches
  static String playerMatches(int id) => '/matches/player/$id';
  static String mostPlayed(int id) => '/matches/player/$id/most-played';

  // Snapshots
  static String playerSnapshots(int id) => '/snapshots/player/$id';
  static const String createSnapshot = '/snapshots/';
  static String snapshotJob(String jobId) => '/snapshots/jobs/$jobId';
  static String deleteSnapshot(int id) => '/snapshots/$id';
  static String updateSnapshotNotes(int id) => '/snapshots/$id/notes';
  static String updateSnapshotDescription(int id) =>
      '/snapshots/$id/description';
  static String snapshotMatches(int id) => '/matches/snapshot/$id';
  static String snapshotStats(int id) => '/matches/snapshot/$id/stats';
  static String snapshotDashboard(int id) => '/snapshots/$id/dashboard';

  // DDragon
  static const String ddragonVersion = '/ddragon/version';
  static const String ddragonSpells = '/ddragon/spells';
  static const String ddragonItems = '/ddragon/items';
  static const String ddragonRunes = '/ddragon/runes';
  static const String ddragonMap = '/ddragon/map';
  static const String ddragonMapUrl = '/ddragon/map/url';

  // League
  static const String rankCutoffs = '/league/cutoffs';

  // Admin
  static const String adminUsers = '/admin/users/';
  static const String adminStats = '/admin/stats/';
  static String adminUserRole(int id) => '/admin/users/$id/role';
  static String adminUserActive(int id) => '/admin/users/$id/active';
  static String adminUser(int id) => '/admin/users/$id';
  static const String adminUsersInactive = '/admin/users/inactive';
  static const String adminPlayers = '/admin/players/';
  static String adminPlayer(int id) => '/admin/players/$id';
}
