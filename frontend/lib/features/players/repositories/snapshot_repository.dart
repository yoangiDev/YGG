import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../models/snapshot_model.dart';
import '../models/snapshot_dashboard_model.dart';

class SnapshotJobStatus {
  const SnapshotJobStatus({required this.status, this.snapshotId, this.progress = 0, this.error});
  final String  status;
  final int?    snapshotId;
  final int     progress;
  final String? error;

  factory SnapshotJobStatus.fromJson(Map<String, dynamic> j) => SnapshotJobStatus(
    status:     j['status']      as String,
    snapshotId: j['snapshot_id'] as int?,
    progress:   j['progress']    as int? ?? 0,
    error:      j['error']       as String?,
  );
}

class SnapshotRepository {
  final _dio = ApiClient.instance.dio;

  Future<List<SnapshotModel>> listForPlayer(int playerId) async {
    final res = await _dio.get(Endpoints.playerSnapshots(playerId));
    final data = res.data as List<dynamic>;
    return data.map((e) => SnapshotModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<String> create({
    required int    playerId,
    required int    dateFrom,
    required int    dateTo,
    String          description = '',
  }) async {
    final res = await _dio.post(Endpoints.createSnapshot, data: {
      'player_id':   playerId,
      'date_from':   dateFrom,
      'date_to':     dateTo,
      'description': description,
    });
    return res.data['job_id'] as String;
  }

  Future<SnapshotJobStatus> jobStatus(String jobId) async {
    final res = await _dio.get(Endpoints.snapshotJob(jobId));
    return SnapshotJobStatus.fromJson(res.data as Map<String, dynamic>);
  }

  Future<void> delete(int snapshotId) async {
    await _dio.delete(Endpoints.deleteSnapshot(snapshotId));
  }

  Future<void> updateNotes(int snapshotId, String notes) async {
    await _dio.patch(Endpoints.updateSnapshotNotes(snapshotId), data: {'notes': notes});
  }

  Future<void> updateDescription(int snapshotId, String description) async {
    await _dio.patch(Endpoints.updateSnapshotDescription(snapshotId), data: {'description': description});
  }

  Future<SnapshotDashboardModel> getDashboard(int snapshotId) async {
    final res = await _dio.get(Endpoints.snapshotDashboard(snapshotId));
    return SnapshotDashboardModel.fromJson(res.data as Map<String, dynamic>);
  }
}
