class AppUser {
  const AppUser({
    required this.id,
    required this.email,
    required this.username,
    required this.role,
    required this.isActive,
    this.avatarUrl,
  });

  final int     id;
  final String  email;
  final String  username;
  final String  role;
  final bool    isActive;
  final String? avatarUrl;

  bool get isAdmin => role == 'admin';

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
    id:        json['id']         as int,
    email:     json['email']      as String,
    username:  json['username']   as String,
    role:      json['role']       as String? ?? 'user',
    isActive:  json['is_active']  as bool?   ?? true,
    avatarUrl: json['avatar_url'] as String?,
  );

  AppUser copyWith({String? role, bool? isActive, String? avatarUrl}) => AppUser(
    id:        id,
    email:     email,
    username:  username,
    role:      role      ?? this.role,
    isActive:  isActive  ?? this.isActive,
    avatarUrl: avatarUrl ?? this.avatarUrl,
  );
}
