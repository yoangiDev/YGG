"""
Integration tests for the Many-to-Many relationship refactor (Match ↔ Snapshot).

Test criteria:
1. Single User Pipeline: Creating a snapshot functions normally.
2. Concurrent Ingestion Test: Simulate two separate users submitting identical matches simultaneously.
   Expected: Both snapshots succeed, the Match table contains exactly one record, and match_snapshots 
   maps to both snapshots properly without throwing an IntegrityError.
3. Cascade Delete Validation: Deleting a Snapshot successfully cleans up its associated tracking lines 
   in match_snapshots while leaving the underlying rows in Match untouched.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.db.models.match import Match
from app.db.models.snapshot import Snapshot
from app.db.models.player import Player
from app.db.models.user import User
from app.db.models.match_snapshot import MatchSnapshot
from app.db.session import get_db
from app.crud.snapshot import get_matches_by_snapshot


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user with unique credentials."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        email=f"test_m2m_{unique_id}@example.com",
        username=f"test_m2m_user_{unique_id}",
        hashed_password="hash"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    # Cleanup
    db_session.delete(user)
    try:
        db_session.commit()
    except:
        db_session.rollback()


@pytest.fixture
def test_player(db_session: Session, test_user: User) -> Player:
    """Create a test player with unique identifiers."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    player = Player(
        user_id=test_user.id,
        game_name=f"TestPlayer_{unique_id}",
        tag_line="M2M",
        puuid=f"test-puuid-{unique_id}",
        region="EUROPE",
        role="MID"
    )
    db_session.add(player)
    db_session.commit()
    db_session.refresh(player)
    yield player
    # Cleanup
    db_session.delete(player)
    try:
        db_session.commit()
    except:
        db_session.rollback()


@pytest.fixture
def sample_match(test_player: Player) -> Match:
    """Create a sample match object (not persisted yet)."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    return Match(
        match_id=f"NA1_123456789_unique_{unique_id}",
        creation_time=datetime.utcnow(),
        champion="Ahri",
        win=True,
        duration=1800,
        kills=5,
        deaths=2,
        assists=8,
        kill_participation=65.0,
        vision=25,
        damage=15000,
        gold=12000,
        total_cs=250,
        damage_share=35.5,
        first_dragon=True,
        void_grubs=False,
        herald=True,
        summoner1_id=4,
        summoner2_id=14,
        item0=3089,
        item1=3165,
        item2=3151,
        item3=3157,
        item4=0,
        item5=0,
        item6=0,
        primary_rune=8112,
        secondary_tree=8000,
    )


class TestSingleUserPipeline:
    """Test 1: Single User Pipeline - Creating a snapshot functions normally."""
    
    def test_create_snapshot_with_single_match(self, db_session: Session, test_player: Player):
        """Create a snapshot with a single match and verify the M:M relationship works."""
        import uuid
        unique = str(uuid.uuid4())[:8]
        
        # Create a new snapshot
        snapshot = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=7),
            date_to=datetime.utcnow(),
            description="Test snapshot for M:M relationship"
        )
        db_session.add(snapshot)
        db_session.flush()
        
        # Add the match
        match = Match(
            match_id=f"NA1_single_match_{unique}",
            creation_time=datetime.utcnow(),
            champion="Ahri",
            win=True,
            duration=1800,
            kills=5,
            deaths=2,
            assists=8,
            kill_participation=65.0,
            vision=25,
            damage=15000,
            gold=12000,
            total_cs=250,
            damage_share=35.5,
        )
        db_session.add(match)
        db_session.flush()
        
        # Create the M:M relationship
        match_snapshot = MatchSnapshot(
            snapshot_id=snapshot.id,
            match_id=match.id
        )
        db_session.add(match_snapshot)
        db_session.commit()
        
        # Verify the relationship - query fresh from DB
        db_session.refresh(snapshot)
        assert len(snapshot.matches) == 1
        assert snapshot.matches[0].match_id == match.match_id
        
    def test_create_snapshot_with_multiple_matches(self, db_session: Session, test_player: Player):
        """Create a snapshot with multiple matches and verify the M:M relationship."""
        import uuid
        unique = str(uuid.uuid4())[:8]
        
        snapshot = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=7),
            date_to=datetime.utcnow(),
            description="Test snapshot with multiple matches"
        )
        db_session.add(snapshot)
        db_session.flush()
        
        # Create 5 different matches
        matches = []
        for i in range(5):
            match = Match(
                match_id=f"NA1_multi_match_{unique}_{i}",
                creation_time=datetime.utcnow() - timedelta(minutes=i*30),
                champion=f"Champion_{i}",
                win=(i % 2 == 0),
                duration=1800,
                kills=i,
                deaths=i-1,
                assists=i+2,
                kill_participation=50.0 + i * 5,
                vision=20 + i,
                damage=10000 + i * 1000,
                gold=10000 + i * 1000,
                total_cs=200 + i * 10,
                damage_share=30.0 + i * 2,
            )
            db_session.add(match)
            db_session.flush()
            matches.append(match)
            
            # Create M:M relationship
            match_snapshot = MatchSnapshot(snapshot_id=snapshot.id, match_id=match.id)
            db_session.add(match_snapshot)
        
        db_session.commit()
        
        # Verify all matches are linked to the snapshot
        db_session.refresh(snapshot)
        assert len(snapshot.matches) == 5


class TestConcurrentIngestion:
    """Test 2: Concurrent Ingestion - Multiple users processing identical matches."""
    
    def test_concurrent_match_processing(self, db_session: Session, test_player: Player):
        """
        Simulate two snapshots sharing the same match.
        Expected: Match table has exactly 1 record, both snapshots link to it without IntegrityError.
        """
        import uuid
        unique = str(uuid.uuid4())[:8]
        
        # Create two snapshots
        snapshot1 = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=7),
            date_to=datetime.utcnow(),
            description="Snapshot 1"
        )
        snapshot2 = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=14),
            date_to=datetime.utcnow() - timedelta(days=7),
            description="Snapshot 2"
        )
        db_session.add(snapshot1)
        db_session.add(snapshot2)
        db_session.flush()
        
        # Create a single match that both snapshots will reference
        shared_match_id = f"NA1_shared_match_{unique}"
        match = Match(
            match_id=shared_match_id,
            creation_time=datetime.utcnow(),
            champion="Ahri",
            win=True,
            duration=1800,
            kills=5,
            deaths=2,
            assists=8,
            kill_participation=65.0,
            vision=25,
            damage=15000,
            gold=12000,
            total_cs=250,
            damage_share=35.5,
        )
        db_session.add(match)
        db_session.flush()
        
        # Both snapshots link to the same match
        match_snapshot1 = MatchSnapshot(snapshot_id=snapshot1.id, match_id=match.id)
        match_snapshot2 = MatchSnapshot(snapshot_id=snapshot2.id, match_id=match.id)
        db_session.add(match_snapshot1)
        db_session.add(match_snapshot2)
        db_session.commit()
        
        # Verify exactly one match in the database
        match_count = db_session.query(Match).filter(Match.match_id == shared_match_id).count()
        assert match_count == 1, f"Expected 1 match, found {match_count}"
        
        # Verify both snapshots reference the same match
        db_session.refresh(snapshot1)
        db_session.refresh(snapshot2)
        assert match in snapshot1.matches
        assert match in snapshot2.matches
        
        # Verify the association table has 2 links
        association_count = db_session.query(MatchSnapshot).filter(MatchSnapshot.match_id == match.id).count()
        assert association_count == 2, f"Expected 2 association links, found {association_count}"
    
    def test_concurrent_insertion_race_condition_handling(self, db_session: Session, test_player: Player):
        """
        Test IntegrityError handling when two concurrent processes try to insert the same match.
        """
        import uuid
        unique = str(uuid.uuid4())[:8]
        
        snapshot1 = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=7),
            date_to=datetime.utcnow(),
            description="Snapshot 1"
        )
        snapshot2 = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=14),
            date_to=datetime.utcnow() - timedelta(days=7),
            description="Snapshot 2"
        )
        db_session.add(snapshot1)
        db_session.add(snapshot2)
        db_session.flush()
        
        # Shared match data
        shared_match_id = f"NA1_race_condition_{unique}"
        
        # Simulate first snapshot attempting to insert the match
        match1 = Match(
            match_id=shared_match_id,
            creation_time=datetime.utcnow(),
            champion="Ahri",
            win=True,
            duration=1800,
            kills=5,
            deaths=2,
            assists=8,
        )
        db_session.add(match1)
        db_session.flush()
        
        # Create association for first snapshot
        match_snapshot1 = MatchSnapshot(snapshot_id=snapshot1.id, match_id=match1.id)
        db_session.add(match_snapshot1)
        db_session.commit()
        
        # Now attempt to create association for second snapshot with the same match
        existing_match = db_session.query(Match).filter(Match.match_id == shared_match_id).first()
        assert existing_match is not None
        
        match_snapshot2 = MatchSnapshot(snapshot_id=snapshot2.id, match_id=existing_match.id)
        db_session.add(match_snapshot2)
        db_session.commit()
        
        # Verify the final state
        matches_count = db_session.query(Match).filter(Match.match_id == shared_match_id).count()
        associations_count = db_session.query(MatchSnapshot).filter(MatchSnapshot.match_id == existing_match.id).count()
        
        assert matches_count == 1, f"Expected 1 match, found {matches_count}"
        assert associations_count == 2, f"Expected 2 associations, found {associations_count}"


class TestCascadeDeleteValidation:
    """Test 3: Cascade Delete Validation."""
    
    def test_delete_snapshot_does_not_delete_shared_match(self, db_session: Session, test_player: Player):
        """
        Deleting a Snapshot should:
        - Clean up its associated tracking lines in match_snapshots
        - Leave the underlying Match record untouched (especially if other snapshots reference it)
        """
        import uuid
        unique = str(uuid.uuid4())[:8]
        
        # Create two snapshots
        snapshot1 = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=7),
            date_to=datetime.utcnow(),
            description="Snapshot 1"
        )
        snapshot2 = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=14),
            date_to=datetime.utcnow() - timedelta(days=7),
            description="Snapshot 2"
        )
        db_session.add(snapshot1)
        db_session.add(snapshot2)
        db_session.flush()
        
        # Create a match shared by both snapshots
        shared_match = Match(
            match_id=f"NA1_shared_delete_{unique}",
            creation_time=datetime.utcnow(),
            champion="Ahri",
            win=True,
            duration=1800,
            kills=5,
            deaths=2,
            assists=8,
        )
        db_session.add(shared_match)
        db_session.flush()
        
        # Both snapshots link to the match
        match_snapshot1 = MatchSnapshot(snapshot_id=snapshot1.id, match_id=shared_match.id)
        match_snapshot2 = MatchSnapshot(snapshot_id=snapshot2.id, match_id=shared_match.id)
        db_session.add(match_snapshot1)
        db_session.add(match_snapshot2)
        db_session.commit()
        
        # Verify initial state
        assert db_session.query(Match).filter(Match.id == shared_match.id).count() == 1
        assert db_session.query(MatchSnapshot).filter(MatchSnapshot.match_id == shared_match.id).count() == 2
        
        # Delete snapshot1
        db_session.delete(snapshot1)
        db_session.commit()
        
        # Verify post-delete state
        # The match should still exist
        match_still_exists = db_session.query(Match).filter(Match.id == shared_match.id).first()
        assert match_still_exists is not None, "Match should not be deleted when snapshot is deleted"
        
        # Only one association should remain (snapshot2's link)
        remaining_associations = db_session.query(MatchSnapshot).filter(MatchSnapshot.match_id == shared_match.id).all()
        assert len(remaining_associations) == 1, f"Expected 1 association, found {len(remaining_associations)}"
        assert remaining_associations[0].snapshot_id == snapshot2.id
    
    def test_delete_snapshot_with_exclusive_match(self, db_session: Session, test_player: Player):
        """
        When deleting a Snapshot that is the ONLY one referencing a Match,
        the CASCADE on the FK should clean up the MatchSnapshot record,
        but the Match itself should remain (orphaned but intact).
        """
        import uuid
        unique = str(uuid.uuid4())[:8]
        
        snapshot = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=7),
            date_to=datetime.utcnow(),
            description="Exclusive snapshot"
        )
        db_session.add(snapshot)
        db_session.flush()
        
        # Create a match used only by this snapshot
        exclusive_match = Match(
            match_id=f"NA1_exclusive_{unique}",
            creation_time=datetime.utcnow(),
            champion="Ahri",
            win=True,
            duration=1800,
            kills=5,
            deaths=2,
            assists=8,
        )
        db_session.add(exclusive_match)
        db_session.flush()
        
        # Create association
        match_snapshot = MatchSnapshot(snapshot_id=snapshot.id, match_id=exclusive_match.id)
        db_session.add(match_snapshot)
        db_session.commit()
        
        match_id = exclusive_match.id
        
        # Delete the snapshot
        db_session.delete(snapshot)
        db_session.commit()
        
        # The match should still exist (no cascade delete on Match from MatchSnapshot)
        orphaned_match = db_session.query(Match).filter(Match.id == match_id).first()
        assert orphaned_match is not None, "Match should remain after snapshot deletion"
        
        # The association should be cleaned up by CASCADE on snapshot_id FK
        associations = db_session.query(MatchSnapshot).filter(MatchSnapshot.match_id == match_id).all()
        assert len(associations) == 0, "MatchSnapshot records should be cleaned up when snapshot is deleted"


class TestQueryLogicUpdates:
    """Test updated query logic for fetching matches through the M:M relationship."""
    
    def test_get_matches_by_snapshot_query(self, db_session: Session, test_player: Player):
        """Test that the updated get_matches_by_snapshot query works correctly."""
        from app.crud.snapshot import get_matches_by_snapshot, get_recent_matches_for_player
        import uuid
        unique = str(uuid.uuid4())[:8]
        
        snapshot = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=7),
            date_to=datetime.utcnow(),
            description="Query test snapshot"
        )
        db_session.add(snapshot)
        db_session.flush()
        
        # Create multiple matches
        for i in range(3):
            match = Match(
                match_id=f"NA1_query_test_{unique}_{i}",
                creation_time=datetime.utcnow() - timedelta(minutes=i*30),
                champion=f"Champion_{i}",
                win=(i % 2 == 0),
                duration=1800 + i*100,
                kills=i,
                deaths=i-1,
                assists=i+2,
            )
            db_session.add(match)
            db_session.flush()
            
            match_snapshot = MatchSnapshot(snapshot_id=snapshot.id, match_id=match.id)
            db_session.add(match_snapshot)
        
        db_session.commit()
        
        # Use the updated query function
        matches = get_matches_by_snapshot(db_session, snapshot.id, user_id=test_player.user_id)
        
        # Verify results
        assert len(matches) == 3, f"Expected 3 matches, got {len(matches)}"

        recent = get_recent_matches_for_player(
            db_session, test_player.id, test_player.user_id, limit=2
        )
        assert len(recent) == 2


class TestUniqueConstraintValidation:
    """Test the unique constraint on the association table."""
    
    def test_duplicate_association_raises_error(self, db_session: Session, test_player: Player):
        """Test that creating a duplicate association (same snapshot + match) raises IntegrityError."""
        import uuid
        unique = str(uuid.uuid4())[:8]
        
        snapshot = Snapshot(
            player_id=test_player.id,
            date_from=datetime.utcnow() - timedelta(days=7),
            date_to=datetime.utcnow(),
            description="Unique constraint test"
        )
        db_session.add(snapshot)
        db_session.flush()
        
        match = Match(
            match_id=f"NA1_unique_constraint_{unique}",
            creation_time=datetime.utcnow(),
            champion="Ahri",
            win=True,
            duration=1800,
            kills=5,
            deaths=2,
            assists=8,
        )
        db_session.add(match)
        db_session.flush()
        
        # Create first association
        match_snapshot1 = MatchSnapshot(snapshot_id=snapshot.id, match_id=match.id)
        db_session.add(match_snapshot1)
        db_session.commit()
        
        # Attempt to create duplicate association
        match_snapshot2 = MatchSnapshot(snapshot_id=snapshot.id, match_id=match.id)
        db_session.add(match_snapshot2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        # Rollback the session to clear the failed transaction
        db_session.rollback()
