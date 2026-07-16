import React, { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import {
    Button,
    Card,
    DataTable,
    Snackbar,
    Text,
    TextInput, useTheme} from "react-native-paper";
import { loyaltyApi } from "../../services/apiService";

export default function LoyaltyScreen() {
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const [userId, setUserId] = useState("");
  const [points, setPoints] = useState("");
  const [description, setDescription] = useState("");
  const [referenceId, setReferenceId] = useState("");
  const [account, setAccount] = useState(null);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({
    visible: false,
    text: "",
    error: false,
  });

  const show = (text, error = false) =>
    setSnackbar({ visible: true, text, error });

  const run = async (action, okMessage) => {
    setLoading(true);
    try {
      await action();
      show(okMessage, false);
    } catch (err) {
      show(err instanceof Error ? err.message : "Request failed", true);
    } finally {
      setLoading(false);
    }
  };

  const loadAccount = async () => {
    const data = await loyaltyApi.getAccount(Number(userId));
    setAccount(data);
  };

  const loadActivities = async () => {
    const data = await loyaltyApi.getActivities(Number(userId), { limit: 50 });
    setActivities(Array.isArray(data) ? data : []);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Loyalty (Agent)</Text>

      <Card style={styles.card}>
        <Card.Title title="Customer" />
        <Card.Content>
          <TextInput
            label="User ID"
            value={userId}
            onChangeText={setUserId}
            mode="outlined"
            keyboardType="numeric"
            style={styles.input}
          />
          <View style={styles.row}>
            <Button
              mode="contained"
              onPress={() =>
                run(async () => {
                  await loyaltyApi.createAccount(Number(userId));
                  await loadAccount();
                }, "Loyalty account created")
              }
            >
              Enroll
            </Button>
            <Button
              mode="contained-tonal"
              onPress={() => run(loadAccount, "Account loaded")}
            >
              Load
            </Button>
            <Button
              mode="outlined"
              onPress={() => run(loadActivities, "History loaded")}
            >
              History
            </Button>
          </View>
        </Card.Content>
      </Card>

      <Card style={styles.card}>
        <Card.Title title="Points Action" />
        <Card.Content>
          <TextInput
            label="Points"
            value={points}
            onChangeText={setPoints}
            mode="outlined"
            keyboardType="numeric"
            style={styles.input}
          />
          <TextInput
            label="Reference ID"
            value={referenceId}
            onChangeText={setReferenceId}
            mode="outlined"
            style={styles.input}
          />
          <TextInput
            label="Description"
            value={description}
            onChangeText={setDescription}
            mode="outlined"
            style={styles.input}
          />
          <View style={styles.row}>
            <Button
              mode="contained"
              buttonColor="#16A34A"
              onPress={() =>
                run(async () => {
                  await loyaltyApi.earnPoints(Number(userId), {
                    type: "EARN",
                    points_change: Number(points),
                    description,
                    reference_id: referenceId || undefined,
                  });
                  await Promise.all([loadAccount(), loadActivities()]);
                }, "Points credited")
              }
            >
              Earn
            </Button>
            <Button
              mode="contained"
              buttonColor="#D97706"
              onPress={() =>
                run(async () => {
                  await loyaltyApi.spendPoints(Number(userId), {
                    type: "SPEND",
                    points_change: Number(points),
                    description,
                    reference_id: referenceId || undefined,
                  });
                  await Promise.all([loadAccount(), loadActivities()]);
                }, "Points redeemed")
              }
            >
              Spend
            </Button>
          </View>
        </Card.Content>
      </Card>

      {account && (
        <Card style={styles.card}>
          <Card.Title title="Account" />
          <Card.Content>
            <Text>User ID: {account.user_id}</Text>
            <Text>Points: {account.current_points}</Text>
            <Text>Tier: {account.tier}</Text>
            <Text>
              Updated: {new Date(account.updated_at).toLocaleString()}
            </Text>
          </Card.Content>
        </Card>
      )}

      <Card style={styles.card}>
        <Card.Title title="Activities" />
        <Card.Content>
          <DataTable>
            <DataTable.Header>
              <DataTable.Title>Type</DataTable.Title>
              <DataTable.Title numeric>Points</DataTable.Title>
              <DataTable.Title>Description</DataTable.Title>
              <DataTable.Title>Ref</DataTable.Title>
            </DataTable.Header>
            {activities.map((activity) => (
              <DataTable.Row key={activity.id}>
                <DataTable.Cell>{activity.type}</DataTable.Cell>
                <DataTable.Cell numeric>
                  {activity.points_change}
                </DataTable.Cell>
                <DataTable.Cell>{activity.description || "-"}</DataTable.Cell>
                <DataTable.Cell>{activity.reference_id || "-"}</DataTable.Cell>
              </DataTable.Row>
            ))}
          </DataTable>
        </Card.Content>
      </Card>

      <Snackbar
        visible={snackbar.visible}
        onDismiss={() =>
          setSnackbar((current) => ({ ...current, visible: false }))
        }
        duration={3000}
        style={{ backgroundColor: snackbar.error ? "#DC2626" : "#16A34A" }}
      >
        {snackbar.text}
      </Snackbar>
    </ScrollView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F3F4F6",
  },
  content: {
    padding: 16,
    gap: 12,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
    marginBottom: 8,
  },
  card: {
    borderRadius: 12,
  },
  row: {
    flexDirection: "row",
    gap: 8,
    marginTop: 6,
  },
  input: {
    marginBottom: 8,
  },
});
